"""Conformance tests of DiscoveryResolver against STXT-DISCOVERY-SPEC, over an in-memory file
system: chain building (project ascent, user, system, STXT_PATH), per-namespace precedence
and the resolution errors of section 8."""

import os

from stxt import (
    DiscoveryEntry,
    DiscoveryEnvironment,
    DiscoveryError,
    DiscoveryFileSystem,
    DiscoveryResolver,
    OsDiscoveryFileSystem,
    SystemDiscoveryEnvironment,
)


class MemoryFileSystem(DiscoveryFileSystem):
    """In-memory DiscoveryFileSystem: a flat map of full paths to file contents."""

    def __init__(self, files):
        self.files = dict(files)
        self.dirs = {"/"}
        for file in self.files:
            self.add_empty_dir(self._dirname(file))

    def add_empty_dir(self, path):
        while path is not None:
            self.dirs.add(path)
            path = self.parent_of(path)

    def is_directory(self, path):
        return path in self.dirs

    def list_directory(self, path):
        prefix = "/" if path == "/" else path + "/"
        names = set()
        entries = []
        for candidate in list(self.files) + list(self.dirs):
            if candidate != path and candidate.startswith(prefix):
                name = candidate[len(prefix):].split("/")[0]
                if name not in names:
                    names.add(name)
                    full = prefix + name
                    entries.append(DiscoveryEntry(full, name, full in self.dirs))
        return entries

    def read_file(self, path):
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    def parent_of(self, path):
        return self._dirname(path)

    def join(self, path, name):
        return "/" + name if path == "/" else path + "/" + name

    @staticmethod
    def _dirname(path):
        if path == "/":
            return None
        index = path.rfind("/")
        return "/" if index == 0 else path[:index]


class FakeEnvironment(DiscoveryEnvironment):
    def __init__(self, stxt_path=None, user_dir=None, system_dir=None):
        self.stxt_path = stxt_path
        self.user_dir = user_dir
        self.system_dir = system_dir

    def get_stxt_path(self):
        return self.stxt_path

    def get_user_level_dir(self):
        return self.user_dir

    def get_system_level_dir(self):
        return self.system_dir


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
