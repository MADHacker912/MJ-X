"""
tests.test_skills_ecosystem — Unit tests for mjx.skills (Project NEXUS).
"""

from pathlib import Path
import pytest

from mjx.skills import (
    SkillValidator,
    SkillLoader,
    SkillRegistry,
    SkillExecutor,
    MCPAdapter,
    SkillManifest,
)
from mjx.security.permissions import PermissionCategory, PermissionManager


def test_skill_loader_parses_yaml_frontmatter():
    loader = SkillLoader()
    sample_content = """---
name: code-reviewer
description: Automated code review and anti-slop verification
version: 1.2.0
triggers: [review, audit code, check pr]
permissions: [read_only]
---
# Instructions
Review the given code diff according to clean architecture rules.
"""
    manifest = loader.parse_skill_markdown(sample_content)
    assert manifest is not None
    assert manifest.name == "code-reviewer"
    assert "review" in manifest.triggers
    assert "read_only" in manifest.permissions
    assert "clean architecture" in manifest.system_prompt


def test_skill_validator_rejects_missing_fields_and_invalid_names():
    validator = SkillValidator()

    # Missing description
    rep1 = validator.validate_metadata({"name": "test-skill"})
    assert rep1.is_valid is False
    assert any("description" in e for e in rep1.errors)

    # Invalid name
    rep2 = validator.validate_metadata({"name": "bad skill name!!", "description": "Some skill"})
    assert rep2.is_valid is False
    assert any("Invalid skill name" in e for e in rep2.errors)


def test_skill_registry_indexing_and_lookup():
    reg = SkillRegistry()

    m1 = SkillManifest("web-search", "Search the web for real-time information", triggers=["search", "find"])
    m2 = SkillManifest("calculator", "Perform arithmetic calculations", triggers=["calculate", "math"])

    assert reg.register(m1) is True
    assert reg.register(m2) is True

    # Find by trigger
    results = reg.find_skills_by_trigger("please search for latest news")
    assert len(results) == 1
    assert results[0].name == "web-search"

    # List
    all_s = reg.list_all_skills()
    assert len(all_s) == 2


def test_skill_executor_with_permissions():
    perm = PermissionManager()
    executor = SkillExecutor(permission_mgr=perm)

    manifest = SkillManifest(
        name="reader",
        description="Reads safe files",
        permissions=["read_only"],
        system_prompt="read prompt",
    )

    # Non-sensitive READ_ONLY is auto-allowed
    res = executor.execute_skill(manifest, {"param": "value"})
    assert res.success is True
    assert "reader" in res.output


def test_mcp_adapter_dispatch_and_gemini_schema():
    adapter = MCPAdapter()

    def add_handler(args):
        return args["a"] + args["b"]

    adapter.register_mcp_tool(
        name="add_numbers",
        description="Add two integers",
        input_schema={
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
        },
        handler=add_handler,
    )

    # Gemini tool declaration format check
    decl = adapter.to_gemini_tool_declaration("add_numbers")
    assert decl is not None
    assert decl["name"] == "add_numbers"
    assert "properties" in decl["parameters"]

    # Dispatch check
    res = adapter.dispatch_call("add_numbers", {"a": 10, "b": 32})
    assert res["success"] is True
    assert res["result"] == 42
