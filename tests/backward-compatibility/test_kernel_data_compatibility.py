import pytest
import json
from dataclasses import asdict

from imrabo.kernel.contracts import ExecutionRequest, ExecutionResult

# --- Golden Data Fixtures (representing older versions of the contracts) ---

@pytest.fixture
def old_execution_request_v1_json():
    """
    A serialized ExecutionRequest from a hypothetical v1, with a simpler structure.
    - 'capabilities' might be missing or different type.
    - 'constraints' might have a different default.
    - An 'old_field' might be present which is now ignored.
    """
    return """
    {
        "request_id": "old-req-v1",
        "artifact_ref": "model:legacy/variant:v1",
        "input": {"text": "legacy prompt"},
        "constraints": {"max_tokens": 128},
        "old_field": "should be ignored"
    }
    """

@pytest.fixture
def old_execution_request_v2_json():
    """
    A serialized ExecutionRequest from a hypothetical v2, closer to current,
    but maybe with some nuances.
    """
    return """
    {
        "request_id": "old-req-v2",
        "artifact_ref": "model:current/variant:v2",
        "input": {"prompt_text": "hello v2"},
        "constraints": {"temperature": 0.5, "max_tokens": 256},
        "capabilities": ["stream", "json_output"]
    }
    """

@pytest.fixture
def old_execution_result_v1_json():
    """
    A serialized ExecutionResult from a hypothetical v1, possibly missing 'metrics'
    or having a simpler 'output' structure.
    """
    return """
    {
        "request_id": "old-req-v1",
        "status": "success",
        "output": "Legacy output string",
        "legacy_metric": 100
    }
    """

@pytest.fixture
def old_execution_result_v2_json():
    """
    A serialized ExecutionResult from a hypothetical v2.
    """
    return """
    {
        "request_id": "old-req-v2",
        "status": "completed",
        "output": {"final_text": "Completed V2"},
        "metrics": {"duration_ms": 500}
    }
    """

# --- Backward Compatibility Tests (Kernel Data) ---

def test_execution_request_backward_compatibility_v1(old_execution_request_v1_json):
    """
    Test deserialization of a v1 ExecutionRequest into the current structure.
    Verifies that missing fields take defaults (if applicable) or are handled.
    """
    data = json.loads(old_execution_request_v1_json)
    
    # We must explicitly filter out unknown fields when converting from dict to dataclass
    # or implement a custom from_dict method if we want to ignore them.
    # For now, dataclasses will raise TypeError if an unknown field is passed directly.
    # So, we'll manually filter if it's not a Pydantic model.
    valid_keys = set(f.name for f in ExecutionRequest.__dataclass_fields__.values())
    filtered_data = {k: v for k, v in data.items() if k in valid_keys}

    request = ExecutionRequest(**filtered_data)
    
    assert request.request_id == "old-req-v1"
    assert request.artifact_ref == "model:legacy/variant:v1"
    assert request.input == {"text": "legacy prompt"}
    assert request.constraints == {"max_tokens": 128}
    assert request.capabilities == [] # Missing in v1, should default to empty list

def test_execution_request_backward_compatibility_v2(old_execution_request_v2_json):
    """
    Test deserialization of a v2 ExecutionRequest.
    """
    data = json.loads(old_execution_request_v2_json)
    request = ExecutionRequest(**data)
    
    assert request.request_id == "old-req-v2"
    assert request.artifact_ref == "model:current/variant:v2"
    assert request.input == {"prompt_text": "hello v2"}
    assert request.constraints == {"temperature": 0.5, "max_tokens": 256}
    assert request.capabilities == ["stream", "json_output"]


def test_execution_result_backward_compatibility_v1(old_execution_result_v1_json):
    """
    Test deserialization of a v1 ExecutionResult into the current structure.
    Verifies that missing fields take defaults and extra fields are ignored.
    """
    data = json.loads(old_execution_result_v1_json)
    
    valid_keys = set(f.name for f in ExecutionResult.__dataclass_fields__.values())
    filtered_data = {k: v for k, v in data.items() if k in valid_keys}

    result = ExecutionResult(**filtered_data)

    assert result.request_id == "old-req-v1"
    assert result.status == "success"
    assert result.output == "Legacy output string"
    assert result.metrics == {} # 'legacy_metric' ignored, 'metrics' defaults to empty dict


def test_execution_result_backward_compatibility_v2(old_execution_result_v2_json):
    """
    Test deserialization of a v2 ExecutionResult.
    """
    data = json.loads(old_execution_result_v2_json)
    result = ExecutionResult(**data)
    
    assert result.request_id == "old-req-v2"
    assert result.status == "completed"
    assert result.output == {"final_text": "Completed V2"}
    assert result.metrics == {"duration_ms": 500}


def test_kernel_contracts_forward_compatibility():
    """
    Test that current contracts can be serialized and deserialized
    without loss of information or errors.
    """
    req_current = ExecutionRequest(
        request_id="current-req",
        artifact_ref="model:new/variant:latest",
        input={"new_field": True},
        constraints={"timeout": 60},
        capabilities=["new_cap"]
    )
    res_current = ExecutionResult(
        request_id="current-req",
        status="completed",
        output={"content": "new result"},
        metrics={"latency": 10.5}
    )

    req_json = json.dumps(asdict(req_current))
    res_json = json.dumps(asdict(res_current))

    # Deserialize back
    deserialized_req = ExecutionRequest(**json.loads(req_json))
    deserialized_res = ExecutionResult(**json.loads(res_json))

    assert deserialized_req == req_current
    assert deserialized_res == res_current

