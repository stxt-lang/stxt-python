"""In-memory host adapters for the discovery tests: a file system rooted at ``/`` with
'/'-separated paths, and a fixed environment. Shared by ``test_discovery.py`` and the conformance
kit runner."""

from stxt import DiscoveryEntry, DiscoveryEnvironment, DiscoveryFileSystem


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
