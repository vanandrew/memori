import os
from pathlib import Path
import logging
from functools import wraps
from contextlib import contextmanager
from typing import Callable


def get_wrapped_callable(func: Callable) -> Callable:
    """Returns the original callable wrapped by a decorator.

    Parameters
    ----------
    func: Callable
        A callable (function) wrapped by a decorator and has the
        __wrapped__ property defined.

    Returns
    -------
    Callable
        The original callable unwrapped from decorators.
    """
    # check __wrapped__ property of callable
    if "__wrapped__" in dir(func):
        # make recursive call unwrap another layer of decorator
        # if it exists.
        return get_wrapped_callable(func.__wrapped__)

    # return the callable
    return func


def create_output_path(func: Callable) -> Callable:
    """Decorator for creating output path before calling function.

    This decorator makes a output path by using the `output_path`
    argument of the calling function. If the `output_path` argument
    does not exist, this decorator will raise a *ValueError*.

    Parameters
    ----------
    func: Callable
        A callable (function) that has `output_path` as an argument.

    Returns
    -------
    Callable
        A wrapped callable (function).
    """
    # raise errors if no output path
    if "output_path" not in get_wrapped_callable(func).__code__.co_varnames:
        raise ValueError("output_path not found in %s" % get_wrapped_callable(func).__name__)

    # wrap function
    @wraps(get_wrapped_callable(func))
    def wrapped(output_path, *args, **kwargs):
        # create the output path
        os.makedirs(output_path, exist_ok=True)

        # call/return func
        return func(output_path, *args, **kwargs)

    # return wrapped function
    return wrapped


def use_abspaths(func: Callable) -> Callable:
    """Decorator that converts all valid path args to absolute paths.

    Parameters
    ----------
    func: Callable
        A callable (function) with valid path arguments.

    Returns
    -------
    Callable
        Callable with valid path arguments replaced with absolute paths.
    """
    # wrap the function
    @wraps(func)
    def wrapped(*args, **kwargs):
        # loop through args and kwargs and search for valid file paths
        mod_args = list()
        for a in args:
            # if valid path
            if isinstance(a, str) and os.path.isfile(a):
                mod_args.append(os.path.abspath(a))
            else:  # just use the original argument
                mod_args.append(a)
        mod_kwargs = dict()
        for key in kwargs:
            # if valid path and key in arg_names
            if isinstance(kwargs[key], str) and os.path.isfile(kwargs[key]):
                mod_kwargs[key] = os.path.abspath(kwargs[key])
            else:  # just use original keyword argument
                mod_kwargs[key] = kwargs[key]

        # run function
        return func(*mod_args, **mod_kwargs)

    # return wrapped
    return wrapped


def create_symlinks_to_input_files(symlink_dir: str = "input_data") -> Callable:
    """Decorator that create symlinks to input_files in specified directory.

    This will create symlinks to all valid files and place then
    in symlink_dir.

    Parameters
    ----------
    symlink_dir: str
        Name of directory to make and place symlinks in.

    Returns
    -------
    Callable
        A wrapped callable (function).
    """
    # return symlinks decorator
    def decorator(func: Callable) -> Callable:
        # get arguments of callable
        num_args = get_wrapped_callable(func).__code__.co_argcount
        arg_names = get_wrapped_callable(func).__code__.co_varnames[:num_args]

        # wrap the function
        @wraps(func)
        def wrapped(*args, **kwargs):
            # make the symlinks directory
            os.makedirs(symlink_dir, exist_ok=True)

            # construct modified args and kwargs list, replacing
            # arguments with valid paths with symlinks
            mod_args = list()
            for a in args:
                # if valid path
                if isinstance(a, str) and os.path.isfile(a):
                    mod_args.append(create_symlink_to_path(a, symlink_dir))
                else:  # just use the original argument
                    mod_args.append(a)
            mod_kwargs = dict()
            for key in kwargs:
                # if valid path and key in arg_names
                if isinstance(kwargs[key], str) and os.path.isfile(kwargs[key]) and key in arg_names:
                    mod_kwargs[key] = create_symlink_to_path(kwargs[key], symlink_dir)
                else:  # just use original keyword argument
                    mod_kwargs[key] = kwargs[key]

            # call the function
            return func(*mod_args, **mod_kwargs)

        # return the wrapper
        return wrapped

    # return decorator
    return decorator


def create_symlink_to_path(filename: str, path_to_symlink: str) -> str:
    """Create a symlink to a file in the specified path.

    Note that path_to_symlink is sensitive to relative paths for
    the return value path.

    Parameters
    ----------
    filename: str
        File to create symlink of
    path_to_symlink: str
        Path (parent directory) to create symlink in

    Returns
    -------
    str
        Path to newly generated symlink
    """
    # get the abspath of the file
    filename = os.path.abspath(filename)

    # get the abspath to the symlink
    path_to_symlink_abs = os.path.abspath(path_to_symlink)

    # get the relative path to the file from the symlink
    relative_path = os.path.relpath(os.path.dirname(filename), path_to_symlink_abs)

    # make symlink path + name
    filesym = os.path.join(path_to_symlink, os.path.basename(filename))

    # make relative path to filename
    filerel = os.path.join(relative_path, os.path.basename(filename))

    # delete existing symlink if it exists
    if os.path.islink(filesym):
        os.unlink(filesym)

    # or if the path is a file, delete it
    if os.path.isfile(filesym):
        os.remove(filesym)

    # now create the symlink
    os.symlink(filerel, filesym)

    # return symbolic link to file
    return filesym


def create_symlink_to_folder(target: Path, symlink_root: Path, symlink_name: str) -> Path:
    """Creates a symlink to target at symlink_root with symlink_name

    Parameters
    ----------
    target: Path
        Target path to link to.
    symlink_root: Path
        Root path to place symlink in.
    symlink_name: str
        Name of symlink.

    Returns
    -------
    Path
        The symlink name
    """
    # get the relative path to the target from the symlink_root
    relative_target = Path(os.path.relpath(target.as_posix(), symlink_root.as_posix()))

    # go to the symlink root
    with working_directory(symlink_root.as_posix(), suppress_log=True):
        if os.path.islink(symlink_name):
            os.unlink(symlink_name)
        if os.path.isfile(symlink_name):
            os.remove(symlink_name)
        Path(symlink_name).symlink_to(relative_target)

    # return the symlink Path
    return symlink_root / symlink_name


@contextmanager
def working_directory(path, suppress_log=False):
    """Changes directory to path, and then changes it back on exit.

    Parameters
    ----------
    path: str
        Change to this path.
    suppress_log: bool
        Flag for suppressing log output.
    """
    # save current directory
    cwd = os.getcwd()

    # change path
    os.chdir(path)
    if not suppress_log:
        logging.info("Changed working directory to: %s", os.getcwd())

    try:  # yield to do stuff
        yield
    finally:  # change back on exit
        os.chdir(cwd)
        if not suppress_log:
            logging.info("Changed working directory to: %s", os.getcwd())


def use_output_path_working_directory(func: Callable) -> Callable:
    """Decorator that changes the current working directory for the function.

    This decorator changes the current working directory for the lifetime
    of the execution of the function to the output_path argument provided
    by the callable.

    Parameters
    ----------
    func: Callable
        A callable (function) that has an output_path argument.

    Returns
    -------
    Callable
        The same callable, but with working directory switched.
    """
    # wrap function
    @wraps(func)
    def wrapped(output_path, *args, **kwargs):
        # Use working directory output_path
        # it will swap back to the original directory
        # on exit of the context manager
        with working_directory(output_path):
            return func(output_path, *args, **kwargs)

    # return wrapped
    return wrapped


def hashable(func: Callable) -> Callable:
    """Decorator that enables a callable to be hashable by memori.

    NOTE: DO NOT PUT THIS ON A RECURSIVE FUNCTION. IT WILL GIVE
    YOU AN INFINITE LOOP!!!

    Parameters
    ----------
    func : Callable
        A callable to decorate.

    Returns
    -------
    Callable
        A callable that is now hashable by memori.
    """
    # recursive function for adding memori hashable attribute to callable
    def add_memori_hashable(c):
        c.__memori_hashable__ = True
        # check if another wrapped function under the current function
        if "__wrapped__" in dir(c):
            add_memori_hashable(c.__wrapped__)

    # wrap the function
    @wraps(func)
    def wrapped(*args, **kwargs):
        return func(*args, **kwargs)

    # add __memori_hashable__ attribute to callable and its wrappers
    add_memori_hashable(wrapped)

    # return decorator
    return wrapped
