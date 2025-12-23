import pytest
from unittest.mock import patch, mock_open, MagicMock
from pathlib import Path
import json
import hashlib
import requests_mock

from imrabo.adapters.storage_fs import FileSystemArtifactResolver
from imrabo.kernel.contracts import ArtifactHandle
from imrabo.internal import paths # For constants like MODEL_REGISTRY_FILE_NAME

# --- Fixtures ---

@pytest.fixture
def mock_models_registry_path(tmp_path):
    """Creates a dummy models.json file and returns its path."""
    registry_data = {
        "schema_version": 1,
        "models": {
            "test-model": {
                "id": "test-model",
                "description": "A test model",
                "min_ram_gb": 4,
                "variants": [
                    {
                        "id": "v1",
                        "files": [
                            {"filename": "model-v1.gguf", "url": "http://example.com/model-v1.gguf", "sha256": "a" * 64},
                            {"filename": "tokenizer.json", "url": "http://example.com/tokenizer.json", "sha256": "b" * 64},
                        ]
                    },
                    {
                        "id": "v2",
                        "files": [
                            {"filename": "model-v2.gguf", "url": "http://example.com/model-v2.gguf", "sha256": "c" * 64},
                        ]
                    }
                ]
            }
        }
    }
    registry_file = tmp_path / "models.json"
    registry_file.write_text(json.dumps(registry_data))
    return registry_file

@pytest.fixture
def mock_invalid_registry_path(tmp_path):
    """Creates a malformed models.json file."""
    registry_file = tmp_path / "malformed_models.json"
    registry_file.write_text("this is not json")
    return registry_file

@pytest.fixture
def mock_models_dir(tmp_path):
    """Creates a temporary directory for local models."""
    models_dir = tmp_path / "imrabo_models"
    models_dir.mkdir()
    return models_dir

@pytest.fixture
def resolver(mock_models_registry_path, mock_models_dir):
    """Provides an instance of FileSystemArtifactResolver."""
    return FileSystemArtifactResolver(registry_path=mock_models_registry_path, models_dir=mock_models_dir)

# --- Tests ---

def test_resolver_init_success(resolver):
    """Test successful initialization of the resolver."""
    assert resolver is not None
    assert "test-model" in resolver._models

def test_resolver_init_registry_not_found(mock_models_dir):
    """Test init fails if registry file is not found."""
    with pytest.raises(RuntimeError, match="Model registry not found"):
        FileSystemArtifactResolver(registry_path=Path("nonexistent.json"), models_dir=mock_models_dir)

def test_resolver_init_malformed_registry(mock_invalid_registry_path, mock_models_dir):
    """Test init fails if registry file is malformed JSON."""
    with pytest.raises(json.JSONDecodeError):
        FileSystemArtifactResolver(registry_path=mock_invalid_registry_path, models_dir=mock_models_dir)

def test_resolve_artifact_not_found(resolver):
    """Test resolving a non-existent artifact."""
    handle = resolver.resolve("model:non-existent/variant:v1")
    assert handle.is_available is False
    assert handle.location is None

def test_resolve_artifact_available(resolver, mock_models_dir):
    """Test resolving an artifact that is locally available."""
    # Simulate model files being present
    (mock_models_dir / "test-model" / "model-v1.gguf").touch()
    (mock_models_dir / "test-model" / "tokenizer.json").touch()

    handle = resolver.resolve("model:test-model/variant:v1")
    assert handle.is_available is True
    assert handle.location == mock_models_dir / "test-model" / "model-v1.gguf"
    assert "test-model" in handle.metadata["id"]

def test_resolve_artifact_partially_available(resolver, mock_models_dir):
    """Test resolving an artifact where only some files are present."""
    (mock_models_dir / "test-model" / "tokenizer.json").touch() # Only one file
    handle = resolver.resolve("model:test-model/variant:v1")
    assert handle.is_available is False # Because model-v1.gguf is missing
    assert handle.location == mock_models_dir / "test-model" # Location still points to base dir


def test_ensure_available_success(resolver, mock_models_dir, requests_mock):
    """Test successful download and verification of an artifact."""
    # Mock hashlib to return expected SHAs (for _calculate_sha256)
    with patch('hashlib.sha256') as mock_sha256:
        mock_sha256.return_value.hexdigest.side_effect = ["a" * 64, "b" * 64] # For model-v1 and tokenizer

        requests_mock.get("http://example.com/model-v1.gguf", content=b"dummy_model_content_v1")
        requests_mock.get("http://example.com/tokenizer.json", content=b"dummy_tokenizer_content")

        handle = resolver.ensure_available("model:test-model/variant:v1")

        assert handle.is_available is True
        assert handle.location == mock_models_dir / "test-model" / "model-v1.gguf"
        assert (mock_models_dir / "test-model" / "model-v1.gguf").exists()
        assert (mock_models_dir / "test-model" / "tokenizer.json").exists()

def test_ensure_available_download_error(resolver, mock_models_dir, requests_mock):
    """Test ensure_available handles network download errors."""
    requests_mock.get("http://example.com/model-v1.gguf", exc=requests.exceptions.RequestException("Network error"))

    with pytest.raises(RuntimeError, match="Failed to download and verify"):
        resolver.ensure_available("model:test-model/variant:v1")
    
    # Ensure no partial files are left
    assert not (mock_models_dir / "test-model" / "model-v1.gguf").exists()
    assert not (mock_models_dir / "test-model" / ".model-v1.gguf.tmp").exists()

def test_ensure_available_checksum_mismatch_after_download(resolver, mock_models_dir, requests_mock):
    """Test ensure_available handles checksum mismatch after download."""
    # Mock hashlib to return a WRONG SHA
    with patch('hashlib.sha256') as mock_sha256:
        mock_sha256.return_value.hexdigest.side_effect = ["wrong_sha" * 8] # For model-v1.gguf
        
        requests_mock.get("http://example.com/model-v1.gguf", content=b"dummy_model_content_v1")
        requests_mock.get("http://example.com/tokenizer.json", content=b"dummy_tokenizer_content")

        with pytest.raises(RuntimeError, match="Failed to download and verify"):
            resolver.ensure_available("model:test-model/variant:v1")
    
    # Ensure no partial/wrong files are left
    assert not (mock_models_dir / "test-model" / "model-v1.gguf").exists()
    assert not (mock_models_dir / "test-model" / ".model-v1.gguf.tmp").exists()


def test_ensure_available_corrupted_local_file_re_downloads(resolver, mock_models_dir, requests_mock):
    """
    Test that if a local file exists but has wrong checksum, it's re-downloaded.
    """
    model_dir = mock_models_dir / "test-model"
    model_dir.mkdir()
    corrupted_file = model_dir / "model-v1.gguf"
    corrupted_file.write_text("corrupted content") # Create with wrong SHA
    
    # Mock hashlib.sha256 to return the *correct* SHA only after re-download
    with patch('hashlib.sha256') as mock_sha256:
        # First call for corrupted_file will be "corrupted_sha", second for downloaded will be "a"*64
        mock_sha256.return_value.hexdigest.side_effect = ["corrupted_sha" * 8, "a" * 64, "b" * 64]

        # requests_mock for the actual download
        requests_mock.get("http://example.com/model-v1.gguf", content=b"dummy_model_content_v1")
        requests_mock.get("http://example.com/tokenizer.json", content=b"dummy_tokenizer_content")

        handle = resolver.ensure_available("model:test-model/variant:v1")
        assert handle.is_available is True
        assert "dummy_model_content_v1" in (model_dir / "model-v1.gguf").read_text()
        assert requests_mock.called_once

def test_list_available_models(resolver, mock_models_dir):
    """Test listing locally available models."""
    # Create some dummy files to simulate installed models
    (mock_models_dir / "test-model" / "model-v1.gguf").touch()
    (mock_models_dir / "test-model" / "tokenizer.json").touch()
    (mock_models_dir / "another-model" / "another-v1.gguf").touch()

    available_handles = resolver.list_available()
    assert len(available_handles) == 2 # test-model/v1 and another-model/v1 (from partial matching)

    # Check for specific model
    test_model_handle = next((h for h in available_handles if "test-model" in h.ref), None)
    assert test_model_handle is not None
    assert test_model_handle.is_available is True

def test_ensure_available_disk_full(resolver, mock_models_dir, requests_mock):
    """Test ensure_available handles disk full scenario."""
    # Simulate disk full by making shutil.disk_usage raise an error or report 0 free space
    # This requires mocking at a lower level or creating a custom mock for disk_usage
    with patch('shutil.disk_usage', side_effect=OSError("No space left on device")):
        requests_mock.get("http://example.com/model-v1.gguf", content=b"dummy_model_content_v1")
        requests_mock.get("http://example.com/tokenizer.json", content=b"dummy_tokenizer_content")

        with pytest.raises(OSError, match="No space left on device"):
            resolver.ensure_available("model:test-model/variant:v1")

    # Ensure no partial files are left
    assert not (mock_models_dir / "test-model" / "model-v1.gguf").exists()

def test_ensure_available_permission_denied(resolver, mock_models_dir, requests_mock):
    """Test ensure_available handles permission denied scenario."""
    # Make the target directory unwritable
    (mock_models_dir / "test-model").mkdir(exist_ok=True)
    (mock_models_dir / "test-model").chmod(0o444) # Read-only permissions

    requests_mock.get("http://example.com/model-v1.gguf", content=b"dummy_model_content_v1")
    requests_mock.get("http://example.com/tokenizer.json", content=b"dummy_tokenizer_content")

    with pytest.raises(PermissionError):
        resolver.ensure_available("model:test-model/variant:v1")
    
    (mock_models_dir / "test-model").chmod(0o777) # Restore permissions for cleanup
