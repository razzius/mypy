"""Watch parts of the file system for changes."""

from mypy.fscache import FileSystemCache
from typing import NamedTuple, Set, AbstractSet, Iterable, Dict, Optional


FileData = NamedTuple('FileData', [('st_mtime', float),
                                   ('st_size', int),
                                   ('md5', str)])


class FileSystemWatcher:
    """Watcher for file system changes among specific paths.

    All file system access is performed using FileSystemCache. We
    detect changed files by stat()ing them all and comparing md5 hashes
    of potentially changed files. If a file has both size and mtime
    unmodified, the file is assumed to be unchanged.

    An important goal of this class is to make it easier to eventually
    use file system events to detect file changes.

    Note: This class doesn't flush the file system cache. If you don't
    manually flush it, changes won't be seen.
    """

    # TODO: Watching directories?
    # TODO: Handle non-files

    def __init__(self, fs: FileSystemCache) -> None:
        self.fs = fs
        self._paths = set()  # type: Set[str]
        self._file_data = {}  # type: Dict[str, Optional[FileData]]

    @property
    def paths(self) -> AbstractSet[str]:
        return self._paths

    def set_file_data(self, path: str, data: FileData) -> None:
        self._file_data[path] = data

    def add_watched_paths(self, paths: Iterable[str]) -> None:
        for path in paths:
            if path not in self._paths:
                # By storing None this path will get reported as changed by
                # find_changed if it exists.
                self._file_data[path] = None
        self._paths |= set(paths)

    def remove_watched_paths(self, paths: Iterable[str]) -> None:
        for path in paths:
            if path in self._file_data:
                del self._file_data[path]
        self._paths -= set(paths)

    def _update(self, path: str) -> None:
        st = self.fs.stat(path)
        md5 = self.fs.md5(path)
        self._file_data[path] = FileData(st.st_mtime, st.st_size, md5)

    def find_changed(self) -> Set[str]:
        """Return paths that have changes since the last call, in the watched set."""
        changed = set()
        for path in self._paths:
            old = self._file_data[path]
            try:
                st = self.fs.stat(path)
            except FileNotFoundError:
                if old is not None:
                    # File was deleted.
                    changed.add(path)
                    self._file_data[path] = None
            else:
                if old is None:
                    # File is new.
                    changed.add(path)
                    self._update(path)
                elif st.st_size != old.st_size or st.st_mtime != old.st_mtime:
                    # Only look for changes if size or mtime has changed as an
                    # optimization, since calculating md5 is expensive.
                    new_md5 = self.fs.md5(path)
                    self._update(path)
                    if st.st_size != old.st_size or new_md5 != old.md5:
                        # Changed file.
                        changed.add(path)
        return changed