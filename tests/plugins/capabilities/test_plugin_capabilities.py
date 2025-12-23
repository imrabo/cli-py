import pytest
from unittest.mock import MagicMock

# Define a conceptual representation of a plugin capability
class Capability:
    def __init__(self, id: str, version: str, description: str):
        if not id or not version:
            raise ValueError("Capability ID and version cannot be empty.")
        self.id = id
        self.version = version
        self.description = description

    def __eq__(self, other):
        return isinstance(other, Capability) and self.id == other.id and self.version == other.version

    def __hash__(self):
        return hash((self.id, self.version))

# Define a conceptual PluginManager for testing capability registration
class ConceptualPluginManager:
    def __init__(self):
        self._registered_capabilities = {} # {capability_id: {version: Capability_obj}}
        self.log_messages = []

    def register_capability(self, capability: Capability, plugin_id: str) -> bool:
        if not isinstance(capability, Capability):
            self.log_messages.append(f"ERROR: Plugin {plugin_id} attempted to register non-Capability object.")
            return False

        if capability.id not in self._registered_capabilities:
            self._registered_capabilities[capability.id] = {}
        
        if capability.version in self._registered_capabilities[capability.id]:
            self.log_messages.append(f"WARNING: Plugin {plugin_id} attempted to register duplicate capability: {capability.id} v{capability.version}. Registration ignored.")
            return False # Duplicate registration ignored

        self._registered_capabilities[capability.id][capability.version] = capability
        self.log_messages.append(f"Plugin {plugin_id} registered capability: {capability.id} v{capability.version}")
        return True

    def deregister_capability(self, capability_id: str, plugin_id: str, version: str = None) -> bool:
        if capability_id not in self._registered_capabilities:
            self.log_messages.append(f"WARNING: Plugin {plugin_id} attempted to deregister non-existent capability: {capability_id}.")
            return False

        if version:
            if version in self._registered_capabilities[capability_id]:
                del self._registered_capabilities[capability_id][version]
                self.log_messages.append(f"Plugin {plugin_id} deregistered capability: {capability_id} v{version}.")
                if not self._registered_capabilities[capability_id]:
                    del self._registered_capabilities[capability_id]
                return True
            else:
                self.log_messages.append(f"WARNING: Plugin {plugin_id} attempted to deregister non-existent version: {capability_id} v{version}.")
                return False
        else:
            # Deregister all versions for this capability ID
            del self._registered_capabilities[capability_id]
            self.log_messages.append(f"Plugin {plugin_id} deregistered all versions of capability: {capability_id}.")
            return True
    
    def get_capabilities(self, capability_id: str = None) -> list[Capability]:
        if capability_id:
            return list(self._registered_capabilities.get(capability_id, {}).values())
        return [cap for versions in self._registered_capabilities.values() for cap in versions.values()]


# --- Tests ---

@pytest.fixture
def plugin_manager():
    return ConceptualPluginManager()

def test_plugin_registers_valid_capability(plugin_manager):
    """Test a plugin can successfully register a valid capability."""
    cap = Capability("engine_adapter", "1.0", "Provides an LLM engine adapter.")
    assert plugin_manager.register_capability(cap, "plugin-a") is True
    assert cap in plugin_manager.get_capabilities("engine_adapter")
    assert "Plugin plugin-a registered capability: engine_adapter v1.0" in plugin_manager.log_messages

def test_plugin_rejects_duplicate_capability_registration(plugin_manager):
    """Test that duplicate capability registrations are ignored/warned."""
    cap1 = Capability("engine_adapter", "1.0", "Provides an LLM engine adapter.")
    cap2 = Capability("engine_adapter", "1.0", "Another description, same ID/version.")

    assert plugin_manager.register_capability(cap1, "plugin-a") is True
    assert plugin_manager.register_capability(cap2, "plugin-b") is False # Should be rejected

    assert len(plugin_manager.get_capabilities("engine_adapter")) == 1 # Only one registered
    assert "WARNING: Plugin plugin-b attempted to register duplicate capability: engine_adapter v1.0" in plugin_manager.log_messages

def test_plugin_registers_multiple_versions_of_same_capability(plugin_manager):
    """Test a plugin can register multiple versions of the same capability."""
    cap_v1 = Capability("engine_adapter", "1.0", "Version 1.0 of the engine adapter.")
    cap_v2 = Capability("engine_adapter", "2.0", "Version 2.0 of the engine adapter.")

    assert plugin_manager.register_capability(cap_v1, "plugin-a") is True
    assert plugin_manager.register_capability(cap_v2, "plugin-a") is True

    capabilities = plugin_manager.get_capabilities("engine_adapter")
    assert len(capabilities) == 2
    assert cap_v1 in capabilities
    assert cap_v2 in capabilities

def test_plugin_handles_invalid_capability_definitions(plugin_manager):
    """Test that invalid capability objects are rejected."""
    # Attempt to register a non-Capability object
    assert plugin_manager.register_capability("not a capability", "plugin-x") is False
    assert "ERROR: Plugin plugin-x attempted to register non-Capability object." in plugin_manager.log_messages

    # Test invalid ID/version during Capability creation
    with pytest.raises(ValueError, match="Capability ID and version cannot be empty."):
        Capability("", "1.0", "Invalid")
    with pytest.raises(ValueError, match="Capability ID and version cannot be empty."):
        Capability("id", "", "Invalid")


def test_plugin_capability_removal(plugin_manager):
    """Test that capabilities can be correctly deregistered."""
    cap1 = Capability("engine_adapter", "1.0", "Provides an LLM engine adapter.")
    cap2 = Capability("storage_adapter", "1.0", "Provides a storage adapter.")
    
    plugin_manager.register_capability(cap1, "plugin-a")
    plugin_manager.register_capability(cap2, "plugin-a")

    # Deregister specific version
    assert plugin_manager.deregister_capability("engine_adapter", "plugin-a", "1.0") is True
    assert "engine_adapter" not in plugin_manager._registered_capabilities # No more versions

    # Deregister all versions of a capability
    cap3_v1 = Capability("ui_component", "1.0", "UI.")
    cap3_v2 = Capability("ui_component", "2.0", "UI.")
    plugin_manager.register_capability(cap3_v1, "plugin-b")
    plugin_manager.register_capability(cap3_v2, "plugin-b")
    assert len(plugin_manager.get_capabilities("ui_component")) == 2
    assert plugin_manager.deregister_capability("ui_component", "plugin-b") is True
    assert "ui_component" not in plugin_manager._registered_capabilities

def test_plugin_deregister_nonexistent_capability(plugin_manager):
    """Test deregistering a non-existent capability is handled gracefully."""
    assert plugin_manager.deregister_capability("nonexistent", "plugin-c") is False
    assert "WARNING: Plugin plugin-c attempted to deregister non-existent capability: nonexistent." in plugin_manager.log_messages

def test_plugin_deregister_nonexistent_version(plugin_manager):
    """Test deregistering a non-existent version of an existing capability."""
    cap = Capability("existing_cap", "1.0", "Existing.")
    plugin_manager.register_capability(cap, "plugin-a")
    assert plugin_manager.deregister_capability("existing_cap", "plugin-a", "2.0") is False
    assert "WARNING: Plugin plugin-a attempted to deregister non-existent version: existing_cap v2.0." in plugin_manager.log_messages
    assert "existing_cap" in plugin_manager._registered_capabilities # Still there

