from dataclasses import is_dataclass
from typing import Any
import pytest

from imrabo.kernel.contracts import ExecutionRequest

def test_execution_request_is_dataclass():
    """Verify ExecutionRequest is a dataclass."""
    assert is_dataclass(ExecutionRequest)

def test_execution_request_instantiation_with_valid_data():
    """Test successful instantiation with valid data."""
    request = ExecutionRequest(
        request_id="test-123",
        artifact_ref="model:test/variant:v1",
        input={"text": "hello"},
        constraints={"temp": 0.7},
        capabilities=["stream"]
    )
    assert request.request_id == "test-123"
    assert request.artifact_ref == "model:test/variant:v1"
    assert request.input == {"text": "hello"}
    assert request.constraints == {"temp": 0.7}
    assert request.capabilities == ["stream"]

@pytest.mark.parametrize(
    "field, invalid_value, expected_error, error_msg_regex",
    [
        ("request_id", "", ValueError, "request_id cannot be empty"),
        ("request_id", None, TypeError, "missing a required argument"), # dataclass init enforces this
        ("artifact_ref", "", ValueError, "artifact_ref cannot be empty"),
        ("artifact_ref", None, TypeError, "missing a required argument"),
        ("constraints", "not a dict", TypeError, "argument must be"), # dataclass init enforces this for dict
        ("capabilities", "not a list", TypeError, "argument must be"), # dataclass init enforces this for list
        ("capabilities", [123], TypeError, "All capabilities must be strings"),
        ("capabilities", ["valid", None], TypeError, "All capabilities must be strings"),
        ("capabilities", ["valid", 123], TypeError, "All capabilities must be strings"),
    ]
)
def test_execution_request_invalid_inputs_fail_loudly(field: str, invalid_value: Any, expected_error: type, error_msg_regex: str):
    """Test that invalid inputs for fields raise appropriate errors at instantiation or post-init."""
    valid_args = {
        "request_id": "req-1",
        "artifact_ref": "art-1",
        "input": {},
        "constraints": {},
        "capabilities": []
    }
    
    # Create a copy to modify for the test case
    test_args = valid_args.copy()

    if field == "request_id" and invalid_value == "":
        test_args[field] = invalid_value
        with pytest.raises(expected_error, match=error_msg_regex):
            ExecutionRequest(**test_args)
    elif field == "artifact_ref" and invalid_value == "":
        test_args[field] = invalid_value
        with pytest.raises(expected_error, match=error_msg_regex):
            ExecutionRequest(**test_args)
    elif field in ["capabilities"]:
        test_args[field] = invalid_value
        with pytest.raises(expected_error, match=error_msg_regex):
            ExecutionRequest(**test_args)
    elif invalid_value is None and expected_error == TypeError:
        # Test missing required argument for request_id or artifact_ref
        args_without_field = {k: v for k, v in valid_args.items() if k != field}
        with pytest.raises(expected_error, match=error_msg_regex):
            ExecutionRequest(**args_without_field)
    else:
        # For direct type mismatches that dataclass init enforces (e.g., constraints: dict)
        test_args[field] = invalid_value
        with pytest.raises(expected_error, match=error_msg_regex):
            ExecutionRequest(**test_args)


def test_execution_request_empty_but_valid_requests_pass():
    """Test that requests with empty but valid fields pass."""
    request = ExecutionRequest(
        request_id="req-empty",
        artifact_ref="art-empty",
        input={},
        constraints={},
        capabilities=[]
    )
    assert request.request_id == "req-empty"
    assert request.artifact_ref == "art-empty"
    assert request.input == {}
    assert request.constraints == {}
    assert request.capabilities == []

def test_execution_request_unknown_fields_are_rejected():
    """Test that unknown fields are rejected upon instantiation.
    Dataclasses do not allow unknown fields in __init__ by default."""
    with pytest.raises(TypeError, match="unexpected keyword argument 'unknown_field'"):
        ExecutionRequest(
            request_id="req-1",
            artifact_ref="art-1",
            input={},
            constraints={},
            capabilities=[],
            unknown_field="value" 
        )

def test_execution_request_capabilities_can_be_empty():
    """Test that capabilities list can be empty."""
    request = ExecutionRequest(
        request_id="req-1",
        artifact_ref="art-1",
        input={},
        constraints={},
        capabilities=[]
    )
    assert request.capabilities == []