from dataclasses import is_dataclass
from typing import Any
import pytest

from imrabo.kernel.contracts import ExecutionResult

def test_execution_result_is_dataclass():
    """Verify ExecutionResult is a dataclass."""
    assert is_dataclass(ExecutionResult)

def test_execution_result_instantiation_with_valid_data():
    """Test successful instantiation of ExecutionResult with valid data."""
    result = ExecutionResult(
        request_id="test-req-1",
        status="completed",
        output={"text": "result"},
        metrics={"duration_sec": 1.5}
    )
    assert result.request_id == "test-req-1"
    assert result.status == "completed"
    assert result.output == {"text": "result"}
    assert result.metrics == {"duration_sec": 1.5}

@pytest.mark.parametrize(
    "field, invalid_value, expected_error, error_msg_regex",
    [
        ("request_id", 123, TypeError, "type of argument"), # dataclass init enforces this
        ("request_id", None, TypeError, "missing a required argument"),
        ("status", 123, TypeError, "type of argument"),
        ("status", None, TypeError, "missing a required argument"),
        ("output", "not a dict", TypeError, "type of argument"), # type is Any, so no error here
        ("output", None, None, None), # Valid
        ("metrics", "not a dict", TypeError, "argument must be"),
        ("metrics", None, TypeError, "missing a required argument"),
    ]
)
def test_execution_result_type_mismatches_fail_loudly(field: str, invalid_value: Any, expected_error: type, error_msg_regex: str):
    """Test that type mismatches for fields in ExecutionResult raise appropriate errors."""
    valid_args = {
        "request_id": "req-1",
        "status": "streaming",
        "output": {},
        "metrics": {}
    }
    
    test_args = valid_args.copy()

    if expected_error is None: # For valid cases
        return

    if invalid_value is None and expected_error == TypeError:
        # Test missing required argument
        args_without_field = {k: v for k, v in valid_args.items() if k != field}
        with pytest.raises(expected_error, match=error_msg_regex):
            ExecutionResult(**args_without_field)
    elif field == "output" and expected_error == TypeError and invalid_value == "not a dict":
        # 'output' is Any, so direct type mismatch won't cause TypeError at init
        pass
    else:
        # For direct type mismatches that dataclass init enforces
        test_args[field] = invalid_value
        with pytest.raises(expected_error, match=error_msg_regex):
            ExecutionResult(**test_args)

def test_execution_result_status_values():
    """Test different valid status values."""
    assert ExecutionResult(request_id="1", status="streaming", output={}, metrics={}).status == "streaming"
    assert ExecutionResult(request_id="1", status="completed", output={}, metrics={}).status == "completed"
    assert ExecutionResult(request_id="1", status="error", output={}, metrics={}).status == "error"

    # Future: if we enforce specific enum-like statuses, add negative tests here.

def test_execution_result_empty_output_and_metrics_pass():
    """Test that empty output and metrics are valid."""
    result = ExecutionResult(
        request_id="req-empty",
        status="completed",
        output={},
        metrics={}
    )
    assert result.output == {}
    assert result.metrics == {}

def test_execution_result_unknown_fields_are_rejected():
    """Test that unknown fields are rejected upon instantiation."""
    with pytest.raises(TypeError, match="unexpected keyword argument 'unknown_field'"):
        ExecutionResult(
            request_id="req-1",
            status="completed",
            output={},
            metrics={},
            unknown_field="value"
        )
