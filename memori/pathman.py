from __future__ import annotations
import os
from pathlib import Path


def get_prefix(filename: str) -> str:
    """A convenient function for getting the filename without extension.

    Parameters
    ----------
    filename: str
        Name of file to get the prefix.

    Returns
    -------
    str
        prefix of file.
    """
    # strip filename extension
    name, ext = os.path.splitext(os.path.basename(filename))
    if ext != "":
        return get_prefix(name)
    # return the prefix
    return name


def get_path_and_prefix(filename: str) -> str:
    """Gets prefix but leaves in the path.

    Parameters
    ----------
    filename: str
        Name of file to get the prefix and path.

    Returns
    -------
    str
        prefix of file with path.
    """
    # get directory
    dirname = os.path.dirname(filename)

    # get the prefix
    prefix = get_prefix(filename)

    # return directory + prefix
    return os.path.join(dirname, prefix)


def append_suffix(filename: str, suffix: str) -> str:
    """Appends a suffix to a given filename.

    Parameters
    ----------
    filename: str
        Name of file to get the prefix and path.
    suffix: str
        Suffix to add to filename

    Returns
    -------
    str
        Name of file with suffix
    """
    # get prefix
    prefix = get_path_and_prefix(filename)

    # get the extension
    ext = filename[len(prefix) :]

    # return filename with suffix
    return prefix + suffix + ext


def replace_suffix(filename: str, suffix: str) -> str:
    """Replaces the last suffix in the given filename.

    Parameters
    ----------
    filename: str
        Name of file to get the prefix and path.
    suffix: str
        Suffix to replace in the filename

    Returns
    -------
    str
        Name of file with new suffix
    """
    # get prefix
    prefix = get_path_and_prefix(filename)

    # get the extension
    ext = filename[len(prefix) :]

    # remove last suffix in prefix
    prefix = "_".join(prefix.split("_")[:-1])

    # return filename with suffix
    return prefix + suffix + ext


def delete_suffix(filename: str) -> str:
    """Deletes the last suffix in the given filename.

    Parameters
    ----------
    filename: str
        Name of file to get the prefix and path.

    Returns
    -------
    str
        Name of file with deleted suffix
    """
    # get prefix
    prefix = get_path_and_prefix(filename)

    # get the extension
    ext = filename[len(prefix) :]

    # remove last suffix in prefix
    new_prefix = "_".join(prefix.split("_")[:-1])

    # return filename with new prefix
    return new_prefix + ext


def repath(dirname: str, filename: str) -> str:
    """Changes the directory of a given filename.

    Parameters
    ----------
    dirname: str
        Directory name to use.
    filename: str
        Filename whose path to change.

    Returns
    -------
    str
        Filename with changed path.
    """
    return os.path.join(dirname, os.path.basename(filename))


class PathManager(type(Path())):
    """This class does provides a convienence methods for path manipulation

    Parameters
    ----------
    path: str
       A path to manage
    """

    @property
    def path(self) -> str:
        """Returns the currently managed path as a string

        Returns
        -------
        str
            path as a string
        """
        return self.as_posix()

    def get_prefix(self) -> PathManager:
        """Returns the prefix of the managed path's filename

        Returns
        -------
        PathManager
            prefix of filename
        """
        return PathManager(get_prefix(self.path))

    def get_path_and_prefix(self) -> PathManager:
        """Returns the prefix of the managed path's filename but also with the path

        Returns
        -------
        PathManager
            prefix of filename with path
        """
        return PathManager(get_path_and_prefix(self.path))

    def append_suffix(self, suffix: str) -> PathManager:
        """Appends a suffix to the path, before any file extensions

        Note that this does not automatically add a underscore for you.
        You must do that on your own.

        >>> p = PathManager("/test/directory/file.extension")
        >>> q = p.append_suffix("_suffix")
        >>> # q is now "/test/directory/file_suffix.extension")

        Parameters
        ----------
        suffix : str
            suffix to append

        Returns
        -------
        PathManager
            path with appended suffix
        """
        return PathManager(append_suffix(self.path, suffix))

    def replace_suffix(self, suffix: str) -> PathManager:
        """Replaces the suffix on a path, before any file extension

        A suffix is definied as ending in "_{SUFFIX}". This method
        will replace the last suffix with the provided one.

        >>> p = PathManager("/test/directory/file_suffix.extension")
        >>> q = p.replace_suffix("_suffix2")
        >>> # q is now "/test/directory/file_suffix2.extension")

        Parameters
        ----------
        suffix : str
            suffix to replace the last suffix with

        Returns
        -------
        PathManager
            path with replaced suffix
        """
        return PathManager(replace_suffix(self.path, suffix))

    def delete_suffix(self) -> PathManager:
        """Deletes the suffix on a path, before any file extension

        A suffix is definied as ending in "_{SUFFIX}". This method
        will delete the last suffix.

        >>> p = PathManager("/test/directory/file_suffix.extension")
        >>> q = p.delete_suffix()
        >>> # q is now "/test/directory/file.extension")

        Returns
        -------
        PathManager
            path with deleted suffix
        """
        return PathManager(delete_suffix(self.path))

    def repath(self, dirname: str) -> PathManager:
        """Change the dirname of the currently managed path.

        This will swap the dirname of the currently managed path
        with the provided one.

        >>> p = PathManager("/test/directory/file.extension")
        >>> q = p.repath("/test2/directory2")
        >>> # q is now "/test2/directory2/file_extension"

        Parameters
        ----------
        dirname : str
            directory to change the dirname of the path to

        Returns
        -------
        PathManager
            new path with new dirname
        """
        return PathManager(repath(dirname, self.path))
