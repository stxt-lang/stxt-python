"""Conformance tests of DiscoveryResolver against STXT-DISCOVERY-SPEC, over an in-memory file
system: chain building (project ascent, user, system, STXT_PATH), per-namespace precedence
and the resolution errors of section 8."""

import os

import pytest

from stxt import (
    DiscoveryEntry,
    DiscoveryError,
    DiscoveryResolver,
    OsDiscoveryFileSystem,
    SystemDiscoveryEnvironment,
)

from .discovery_memory import FakeEnvironment, MemoryFileSystem



def template(namespace, root_node):
    return (f"Template (@stxt.template): {namespace}\n\tStructure >>\n"
            f"\t\t{root_node} ({namespace}):\n\t\t\tTitle: (1)\n")


def schema(namespace, root_node):
    return (f"Schema (@stxt.schema): {namespace}\n\tNode: {root_node}\n\t\tChildren:\n"
            f"\t\t\tChild: Title\n\t\t\t\tMin: 1\n\t\t\t\tMax: 1\n\tNode: Title\n")


class TestResolutionChain:
    def test_collects_every_ancestor_stxt_directory_nearest_first_without_stopping_at_the_first_one(self):
        fs = MemoryFileSystem({
            "/repo/.stxt/common.stxt": template("com.acme.common", "Common"),
            "/repo/web/.stxt/web.stxt": template("com.acme.web", "Web"),
            "/repo/web/docs/doc.stxt": "irrelevant",
        })
        assert DiscoveryResolver(fs, FakeEnvironment()).resolve_chain("/repo/web/docs") == ["/repo/web/.stxt", "/repo/.stxt"]

    def test_appends_the_user_and_system_levels_after_the_project_levels(self):
        fs = MemoryFileSystem({
            "/repo/.stxt/a.stxt": template("com.acme.a", "A"),
            "/home/ana/.stxt/b.stxt": template("org.ana.b", "B"),
            "/etc/stxt/c.stxt": template("org.corp.c", "C"),
        })
        resolver = DiscoveryResolver(fs, FakeEnvironment(None, "/home/ana/.stxt", "/etc/stxt"))
        assert resolver.resolve_chain("/repo") == ["/repo/.stxt", "/home/ana/.stxt", "/etc/stxt"]

    def test_ignores_user_and_system_directories_that_do_not_exist(self):
        fs = MemoryFileSystem({"/repo/.stxt/a.stxt": template("com.acme.a", "A")})
        resolver = DiscoveryResolver(fs, FakeEnvironment(None, "/home/ana/.stxt", "/etc/stxt"))
        assert resolver.resolve_chain("/repo") == ["/repo/.stxt"]

    def test_does_not_duplicate_the_user_level_when_the_ascent_already_found_it(self):
        fs = MemoryFileSystem({"/home/ana/.stxt/a.stxt": template("org.ana.a", "A")})
        resolver = DiscoveryResolver(fs, FakeEnvironment(None, "/home/ana/.stxt", None))
        assert resolver.resolve_chain("/home/ana/notes") == ["/home/ana/.stxt"]

    def test_a_document_with_no_location_starts_at_the_user_level(self):
        fs = MemoryFileSystem({
            "/repo/.stxt/a.stxt": template("com.acme.a", "A"),
            "/home/ana/.stxt/b.stxt": template("org.ana.b", "B"),
        })
        resolver = DiscoveryResolver(fs, FakeEnvironment(None, "/home/ana/.stxt", None))
        assert resolver.resolve_chain(None) == ["/home/ana/.stxt"]

    def test_honors_the_max_ascent_safeguard(self):
        fs = MemoryFileSystem({"/a/.stxt/x.stxt": template("com.acme.x", "X")})
        fs.add_empty_dir("/a/b/c/d/e")
        resolver = DiscoveryResolver(fs, FakeEnvironment(), max_ascent=3)
        # The ascent examines /a/b/c/d/e, /a/b/c/d and /a/b/c, and stops before /a.
        assert resolver.resolve_chain("/a/b/c/d/e") == []


class TestStxtPath:
    def test_replaces_the_whole_chain_including_the_project_level(self):
        fs = MemoryFileSystem({
            "/repo/.stxt/a.stxt": template("com.acme.a", "A"),
            "/ci/defs/b.stxt": template("org.ci.b", "B"),
        })
        resolver = DiscoveryResolver(fs, FakeEnvironment(["/ci/defs"], "/home/ana/.stxt", "/etc/stxt"))
        assert resolver.resolve_chain("/repo") == ["/ci/defs"]

    def test_defined_but_empty_leaves_the_chain_empty(self):
        fs = MemoryFileSystem({"/repo/.stxt/a.stxt": template("com.acme.a", "A")})
        resolver = DiscoveryResolver(fs, FakeEnvironment([]))
        assert resolver.resolve_chain("/repo") == []
        assert resolver.resolve("/repo").get_all_schemas() == []

    def test_ignores_nonexistent_entries_and_keeps_the_order_as_precedence(self):
        fs = MemoryFileSystem({
            "/one/a.stxt": template("com.acme.doc", "One"),
            "/two/a.stxt": template("com.acme.doc", "Two"),
        })
        result = DiscoveryResolver(fs, FakeEnvironment(["/missing", "/one", "/two"])).resolve("/anywhere")
        assert result.get_chain() == ["/one", "/two"]
        assert result.get_definition("com.acme.doc").file == "/one/a.stxt"


class TestPerNamespacePrecedence:
    def test_the_nearest_level_wins_for_each_namespace(self):
        fs = MemoryFileSystem({
            "/repo/.stxt/web.stxt": template("com.acme.web", "Old"),
            "/repo/web/.stxt/web.stxt": template("com.acme.web", "New"),
        })
        result = DiscoveryResolver(fs, FakeEnvironment()).resolve("/repo/web")
        assert result.get_definition("com.acme.web").file == "/repo/web/.stxt/web.stxt"
        assert result.get_errors() == [], "a cross-level duplicate is not an error"
        assert len(result.get_all_schemas()) == 1

    def test_different_namespaces_resolve_from_different_levels_in_the_same_validation(self):
        fs = MemoryFileSystem({
            "/repo/web/.stxt/web.stxt": template("com.acme.web", "Web"),
            "/repo/.stxt/common.stxt": template("com.acme.common", "Common"),
            "/home/ana/.stxt/personal.stxt": template("org.ana.notes", "Notes"),
        })
        result = DiscoveryResolver(fs, FakeEnvironment(None, "/home/ana/.stxt", None)).resolve("/repo/web")
        assert result.get_definition("com.acme.web").level_dir == "/repo/web/.stxt"
        assert result.get_definition("com.acme.common").level_dir == "/repo/.stxt"
        assert result.get_definition("org.ana.notes").level_dir == "/home/ana/.stxt"
        assert len(result.get_all_schemas()) == 3

    def test_a_template_at_a_nearer_level_beats_a_schema_at_a_farther_one(self):
        fs = MemoryFileSystem({
            "/repo/.stxt/doc.stxt": schema("com.acme.doc", "Document"),
            "/repo/web/.stxt/doc.stxt": template("com.acme.doc", "Document"),
        })
        result = DiscoveryResolver(fs, FakeEnvironment()).resolve("/repo/web")
        assert result.get_definition("com.acme.doc").file == "/repo/web/.stxt/doc.stxt"

    def test_subdirectories_of_a_resolution_directory_belong_to_the_same_level(self):
        fs = MemoryFileSystem({"/repo/.stxt/sub/dir/a.stxt": template("com.acme.a", "A")})
        result = DiscoveryResolver(fs, FakeEnvironment()).resolve("/repo")
        assert result.get_definition("com.acme.a").level_dir == "/repo/.stxt"


class TestResolutionErrors:
    def test_a_same_level_duplicate_is_an_error_and_leaves_the_namespace_without_active_definition(self):
        fs = MemoryFileSystem({
            "/repo/.stxt/one.stxt": template("com.acme.doc", "One"),
            "/repo/.stxt/two.stxt": schema("com.acme.doc", "Two"),
        })
        result = DiscoveryResolver(fs, FakeEnvironment()).resolve("/repo")
        errors = result.get_errors()
        assert len(errors) == 1
        assert errors[0].code == DiscoveryError.DUPLICATE_NAMESPACE
        assert errors[0].namespace == "com.acme.doc"
        assert result.get_schema("com.acme.doc") is None
        assert result.get_all_schemas() == []

    def test_a_same_level_duplicate_does_not_block_the_other_namespaces(self):
        fs = MemoryFileSystem({
            "/repo/.stxt/one.stxt": template("com.acme.doc", "One"),
            "/repo/.stxt/two.stxt": template("com.acme.doc", "Two"),
            "/repo/.stxt/other.stxt": template("com.acme.other", "Other"),
        })
        result = DiscoveryResolver(fs, FakeEnvironment()).resolve("/repo")
        assert result.get_schema("com.acme.doc") is None
        assert result.get_schema("com.acme.other") is not None, "the non-conflicting namespace keeps working"

    def test_a_nearer_same_level_conflict_does_not_fall_back_to_a_farther_definition_of_that_namespace(self):
        fs = MemoryFileSystem({
            "/repo/.stxt/one.stxt": template("com.acme.doc", "One"),
            "/repo/.stxt/two.stxt": template("com.acme.doc", "Two"),
            "/home/ana/.stxt/farther.stxt": template("com.acme.doc", "Farther"),
        })
        result = DiscoveryResolver(fs, FakeEnvironment(None, "/home/ana/.stxt", None)).resolve("/repo")
        assert result.get_definition("com.acme.doc") is None
        assert result.get_schema("com.acme.doc") is None
        assert not any(d.namespace == "com.acme.doc" for d in result.get_active_definitions())

    def test_a_third_definition_of_the_conflicted_namespace_is_reported_too(self):
        fs = MemoryFileSystem({
            "/repo/.stxt/one.stxt": template("com.acme.doc", "One"),
            "/repo/.stxt/two.stxt": template("com.acme.doc", "Two"),
            "/repo/.stxt/three.stxt": template("com.acme.doc", "Three"),
        })
        errors = DiscoveryResolver(fs, FakeEnvironment()).resolve("/repo").get_errors()
        assert [e.code for e in errors] == [DiscoveryError.DUPLICATE_NAMESPACE] * 2
        assert [e.file for e in errors] == ["/repo/.stxt/three.stxt", "/repo/.stxt/two.stxt"], "sorted by path"

    def test_a_file_that_does_not_parse_is_not_parseable(self):
        fs = MemoryFileSystem({"/repo/.stxt/broken.stxt": "This line has no colon and no block marker\n"})
        errors = DiscoveryResolver(fs, FakeEnvironment()).resolve("/repo").get_errors()
        assert [e.code for e in errors] == [DiscoveryError.NOT_PARSEABLE]

    def test_a_document_of_another_namespace_is_not_a_definition(self):
        fs = MemoryFileSystem({"/repo/.stxt/doc.stxt": "Document (com.acme.doc):\n\tTitle: Hello\n"})
        errors = DiscoveryResolver(fs, FakeEnvironment()).resolve("/repo").get_errors()
        assert [e.code for e in errors] == [DiscoveryError.NOT_A_DEFINITION]

    def test_an_empty_document_is_not_a_definition(self):
        fs = MemoryFileSystem({"/repo/.stxt/empty.stxt": "# nothing here\n"})
        errors = DiscoveryResolver(fs, FakeEnvironment()).resolve("/repo").get_errors()
        assert [e.code for e in errors] == [DiscoveryError.NOT_A_DEFINITION]

    def test_a_non_stxt_file_is_not_a_definition(self):
        fs = MemoryFileSystem({
            "/repo/.stxt/README.md": "# Not a definition\n",
            "/repo/.stxt/good.stxt": template("com.acme.doc", "Doc"),
        })
        result = DiscoveryResolver(fs, FakeEnvironment()).resolve("/repo")
        assert [e.code for e in result.get_errors()] == [DiscoveryError.NOT_A_DEFINITION]
        assert result.get_schema("com.acme.doc") is not None, "the valid definition still loads"

    def test_a_definition_that_fails_its_meta_schema_is_invalid_definition(self):
        fs = MemoryFileSystem({"/repo/.stxt/bad.stxt": "Schema (@stxt.schema): com.acme.bad\n\tBogus: not allowed here\n"})
        errors = DiscoveryResolver(fs, FakeEnvironment()).resolve("/repo").get_errors()
        assert [e.code for e in errors] == [DiscoveryError.INVALID_DEFINITION]


class TestDiscoveryResultAsSchemaProvider:
    def test_serves_the_meta_schemas_of_the_two_reserved_namespaces(self):
        fs = MemoryFileSystem({"/repo/.stxt/a.stxt": template("com.acme.a", "A")})
        result = DiscoveryResolver(fs, FakeEnvironment()).resolve("/repo")
        assert result.get_schema("@stxt.schema") is not None
        assert result.get_schema("@stxt.template") is not None
        assert result.get_schema("com.acme.unknown") is None

    def test_reports_provenance_through_get_active_definitions(self):
        fs = MemoryFileSystem({
            "/repo/.stxt/a.stxt": template("com.acme.a", "A"),
            "/home/ana/.stxt/b.stxt": template("org.ana.b", "B"),
        })
        definitions = DiscoveryResolver(fs, FakeEnvironment(None, "/home/ana/.stxt", None)).resolve("/repo").get_active_definitions()
        assert [(d.namespace, d.level_dir) for d in definitions] == [("com.acme.a", "/repo/.stxt"), ("org.ana.b", "/home/ana/.stxt")]

    def test_caches_loaded_levels_until_clear_cache(self):
        fs = MemoryFileSystem({"/repo/.stxt/a.stxt": template("com.acme.a", "A")})
        resolver = DiscoveryResolver(fs, FakeEnvironment())

        first = resolver.resolve("/repo")
        assert first.get_schema("com.acme.a") is not None

        # The cache serves the same level object, even after the files changed on disk
        fs.files["/repo/.stxt/a.stxt"] = template("com.acme.changed", "A")
        second = resolver.resolve("/repo")
        assert second.get_schema("com.acme.a") is not None
        assert second.get_schema("com.acme.changed") is None

        resolver.clear_cache()
        third = resolver.resolve("/repo")
        assert third.get_schema("com.acme.changed") is not None, "reload after clear_cache sees the change"


class TestBoundedAndTolerantDescent:
    """The recursive descent inside a resolution directory must terminate and tolerate listing
    failures (STXT-DISCOVERY-SPEC §3, §10): a symlink loop, a pathologically deep tree or a
    directory that cannot be listed must never turn resolution into unbounded recursion or an
    escaping exception."""

    def test_a_self_listing_directory_cycle_resolves_without_recursion_error(self):
        # An in-memory file system whose 'loop' subdirectory lists itself forever. Without the
        # depth bound, the descent would recurse until RecursionError.
        class CyclicFileSystem(MemoryFileSystem):
            def list_directory(self, path):
                if path == "/defs/loop":
                    return [DiscoveryEntry("/defs/loop", "loop", True)]
                return super().list_directory(path)

        fs = CyclicFileSystem({
            "/defs/good.stxt": template("com.acme.good", "Good"),
            "/defs/loop/placeholder": "",
        })
        result = DiscoveryResolver(fs, FakeEnvironment(["/defs"])).resolve("/anywhere")
        # It terminates and still loads the legitimate definition found before/around the loop.
        assert result.get_schema("com.acme.good") is not None

    def test_a_pathologically_deep_tree_stops_at_the_descent_limit(self):
        # A chain of nested directories deeper than DEFAULT_MAX_DESCENT (32). A file below the
        # limit is never reached; a file above it is.
        files = {"/defs/near.stxt": template("com.acme.near", "Near")}
        deep = "/defs" + "/d" * 40 + "/far.stxt"
        files[deep] = template("com.acme.far", "Far")
        fs = MemoryFileSystem(files)
        result = DiscoveryResolver(fs, FakeEnvironment(["/defs"])).resolve("/anywhere")
        assert result.get_schema("com.acme.near") is not None
        assert result.get_schema("com.acme.far") is None, "the too-deep file is beyond the descent limit"

    def test_a_subdirectory_that_cannot_be_listed_is_tolerated(self):
        # list_directory raises OSError for one subdirectory; resolve() must not propagate it and
        # the rest of the level must still load.
        class PartlyUnreadableFileSystem(MemoryFileSystem):
            def list_directory(self, path):
                if path == "/defs/secret":
                    raise PermissionError(path)
                return super().list_directory(path)

        fs = PartlyUnreadableFileSystem({
            "/defs/good.stxt": template("com.acme.good", "Good"),
            "/defs/secret/hidden.stxt": template("com.acme.hidden", "Hidden"),
        })
        result = DiscoveryResolver(fs, FakeEnvironment(["/defs"])).resolve("/anywhere")  # must not raise
        assert result.get_schema("com.acme.good") is not None
        assert result.get_schema("com.acme.hidden") is None, "the unreadable subtree contributes nothing"

    def test_os_file_system_does_not_follow_a_real_directory_symlink_loop(self, tmp_path):
        stxt_dir = tmp_path / "project" / ".stxt"
        stxt_dir.mkdir(parents=True)
        (stxt_dir / "a.stxt").write_text(template("com.acme.a", "A"), encoding="utf-8")

        loop = stxt_dir / "loop"
        try:
            os.symlink(stxt_dir, loop, target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("the operating system does not allow creating symbolic links")

        fs = OsDiscoveryFileSystem()
        # The symlink-to-directory is omitted from the listing, so the descent never enters it.
        listed = fs.list_directory(str(stxt_dir))
        assert not any(e.name == "loop" and e.is_directory for e in listed)

        result = DiscoveryResolver(fs, FakeEnvironment()).resolve(str(tmp_path / "project"))  # must terminate
        assert result.get_definition("com.acme.a").file == str(stxt_dir / "a.stxt")


class TestHostAdapters:
    def test_os_file_system_over_a_real_directory(self, tmp_path):
        (tmp_path / "project" / ".stxt").mkdir(parents=True)
        (tmp_path / "project" / ".stxt" / "a.stxt").write_text(template("com.acme.a", "A"), encoding="utf-8")
        (tmp_path / "project" / "docs").mkdir()

        fs = OsDiscoveryFileSystem()
        assert fs.is_directory(str(tmp_path / "project" / ".stxt"))
        assert not fs.is_directory(str(tmp_path / "project" / ".stxt" / "a.stxt"))
        assert fs.parent_of(str(tmp_path / "project")) == str(tmp_path)
        assert fs.parent_of(os.path.abspath(os.sep)) is None
        assert fs.join(str(tmp_path), ".stxt") == str(tmp_path / ".stxt")

        result = DiscoveryResolver(fs, FakeEnvironment()).resolve(str(tmp_path / "project" / "docs"))
        assert result.get_chain() == [str(tmp_path / "project" / ".stxt")]
        assert result.get_definition("com.acme.a").file == str(tmp_path / "project" / ".stxt" / "a.stxt")

    def test_system_environment_reads_stxt_path(self, monkeypatch):
        env = SystemDiscoveryEnvironment()
        monkeypatch.delenv("STXT_PATH", raising=False)
        assert env.get_stxt_path() is None
        monkeypatch.setenv("STXT_PATH", "")
        assert env.get_stxt_path() == []
        monkeypatch.setenv("STXT_PATH", os.pathsep.join(["/one", "/two"]))
        assert env.get_stxt_path() == ["/one", "/two"]
        assert env.get_user_level_dir().endswith(".stxt")
        assert env.get_system_level_dir() is not None
