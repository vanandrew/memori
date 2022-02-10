import importlib
import os
import json
import logging
import hashlib
from types import CodeType, ModuleType
from functools import reduce
from typing import Callable, Dict, List, Tuple, Union
from .helpers import get_wrapped_callable


class Stage:
    """Stage object representing one node of a processing pipeline.

    Constructs a stage object that wraps a callable for use in a pipeline.
    When the `run` method is called the callable is executed and it's
    return value is stored in a result dictionary that can be accessed
    by the `results` property. The return value is parsed into this
    dictionary based on the list provide by `stage_outputs` (The position
    of each string in the list corresponds to each positional return
    value).

    Note: Stage objects convert their results to JSON so they can be
    written to file. This procedure will convert certain data structures
    (e.g. tuples to list, etc) and give unexpected results if not careful.
    In general, the current workaround is to use JSON compatible data
    structures for your function returns.

    Parameters
    ----------
    function_to_call: Callable
        A callable to wrap that the stage executes.
    stage_outputs: List[str]
        A list of strings to label each return value from the function_to_call.
    hash_output: str
        A directory that should be created or checked to cache the stage execution.
    stage_name: str
        Override the name for the stage.

    Methods
    -------
    run:
        Run the stage.
    """

    def __init__(
        self,
        function_to_call: Callable,
        stage_outputs: List = None,
        hash_output: str = None,
        stage_name: str = None,
        **kwargs,
    ):
        # store function_to_call
        self.function_to_call = function_to_call

        # store function input/output names
        func = get_wrapped_callable(self.function_to_call)
        num_of_input_args = func.__code__.co_argcount
        self.stage_inputs = list(func.__code__.co_varnames[:num_of_input_args])
        self.stage_outputs = stage_outputs if stage_outputs else list()
        self.stage_outputs = (
            stage_outputs
            if type(stage_outputs) == list
            else [
                stage_outputs,
            ]
        )

        # save arguments that should be passed on to the stage
        self.stage_args = kwargs

        # create dictionary for collective stage input arguments
        self.stage_input_args = dict()

        # get the stage name from the function_name
        self.stage_name = stage_name if stage_name else function_to_call.__name__

        # create results dictionary
        self.stage_results = dict()

        # store hash location
        self.hash_output = hash_output

        # create hash file locations
        if hash_output:
            self.stage_hash_location = os.path.join(hash_output, "%s.stage" % self.stage_name)
            self.input_hash_location = os.path.join(hash_output, "%s.inputs" % self.stage_name)
            self.output_hash_location = os.path.join(hash_output, "%s.outputs" % self.stage_name)

    def run(
        self,
        *args,
        force_skip_stage: bool = False,
        force_run_stage: bool = False,
        force_hash_write: bool = False,
        **kwargs,
    ) -> Dict:
        """Call function and save outputs in result dictionary.

        Runs the wrapped function_to_call with given args/kwargs.
        If any kwargs were specified on construction of the stage object,
        they will have precedence over any arguments specified in the
        calling `run` method. Hashes for the stage will also be checked to
        detect whether the stage should be run or not.

        Parameters
        ----------
        force_skip_stage: bool
            Specifies whether this stage should be forcefully skipped
        force_run_stage: bool
            Specifies whether this stage should be forcefully run. Has
            precedence over `force_skip_stage`
        force_hash_write: bool
            Specifies whether the hash for this stage should be written out
            even if the stage has not run.
        """
        # flag that specifies whether the current stage has been run
        self.stage_has_run = False

        # convert args/kwargs into one input arg dictionary
        for i, name in enumerate(self.inputs[: len(args)]):
            self.stage_input_args[name] = args[i]
        self.stage_input_args.update(kwargs)

        # override input_args with any stage_args specified
        self.stage_input_args.update(self.stage_args)
        logging.info("Using these arguments for stage: {}\n{}".format(self.stage_name, self.stage_input_args))

        # initialize stage_should_run
        stage_should_run = True

        # check if hash_output is specified (check if the hashes exists
        # for this stage)
        if self.hash_output:
            # check stage hashes
            hashes_matched = self._check_hashes()

            # if hashes matched, then we want to skip running the stage
            if hashes_matched:
                stage_should_run = False

        # check forcing flags
        if force_skip_stage:
            logging.info("Force skip stage: %s", self.stage_name)
            stage_should_run = False
        if force_run_stage:
            logging.info("Force run stage: %s", self.stage_name)
            stage_should_run = True

        # check stage_should_run
        if stage_should_run:
            logging.info("Running stage: %s", self.stage_name)
            # run the function_to_call with the specified input_args
            outputs = self.function_to_call(**self.stage_input_args)
            # make outputs a list, if not a list/tuple
            if not isinstance(outputs, (tuple, list)):
                outputs = [outputs]
            # make outputs the same length as stage_outputs
            outputs = outputs[: len(self.stage_outputs)]
            # store each output in results dictionary
            for stage_out, out in zip(self.stage_outputs, outputs):
                self.stage_results[stage_out] = out
            # set stage_has_run
            self.stage_has_run = True
        else:
            logging.info("Skipping stage: %s execution...", self.stage_name)
            self._load_results_from_hash()

        # write new hashes after stage has run (or if force_hash_write is set)
        if self.hash_output and (self.stage_has_run or force_hash_write):
            self._write_hashes()

        # return results
        return self.stage_results

    def _load_results_from_hash(self) -> None:
        """Load output hash into results"""
        logging.info("Loading cached results...")
        with open(self.output_hash_location, "r") as f:
            self.stage_results = self._unhash_files_in_dict(json.load(f), "file")

    def _write_hashes(self) -> None:
        """Write hashes of stage to file"""
        self._write_stage_hash(self.stage_hash_location, self._get_function_byte_code)
        self._write_io_hash(self.input_hash_location, self.stage_input_args)
        self._write_io_hash(self.output_hash_location, self.stage_results)

    def _check_hashes(self) -> bool:
        """Check hashes of stage"""
        # check the hash location for the stage hash and the input hash
        stage_match = self._check_stage_hash(self.stage_hash_location, self._get_function_byte_code)
        if not stage_match:
            logging.info("Stage hash for stage: %s did not match!", self.stage_name)
        input_match = self._check_io_hash(self.input_hash_location, self.stage_input_args)
        if not input_match:
            logging.info("Input hash for stage: %s did not match!", self.stage_name)
        # check if output hash exists
        output_hash_exists = os.path.exists(self.output_hash_location)
        if output_hash_exists:
            # load stage results from output hash
            self._load_results_from_hash()
            # Why do we load the results from the output hash then check it against itself?
            # We want to rehash the results available on the disk. It could
            # be different if the user decided to delete/move/modify the output
            # files
            output_match = self._check_io_hash(self.output_hash_location, self.stage_results)

            # check if stage_output keys are in the stage_results
            # this is for cases when the developer adds a new stage output key that is currently
            # not present in the current output hash
            for key in self.stage_outputs:
                if key not in self.stage_results:
                    output_match = False
        else:  # return match False
            output_match = False
        if not output_match:
            logging.info("Output hash for stage: %s did not match!", self.stage_name)

        # return if all checks True or if at least one is False
        return stage_match and input_match and output_hash_exists and output_match

    def _hash_files_in_dict(self, io_dict: Dict) -> Dict:
        """Replaces valid paths in Dict with a special 'file' dict.

        This method replaces valid, existing paths with a dict
        containing the following:

            { "file": file_path, "hash": sha256_hash }

        Parameters
        ----------
        io_dict: Dict
            Dictionary to replace paths with 'file' dict.

        Returns
        -------
        Dict
            A dictionary with all paths replace with 'file' dicts.
        """
        new_dict = io_dict.copy()

        # loop over keys in dictionary
        for key in new_dict:
            # get value at key
            value = new_dict[key]

            # test if value is an existing file
            if isinstance(value, str) and os.path.isfile(value):
                # obtain hash for file
                file_hash = self._hash_file(value)

                # replace with 'file' dict
                new_dict[key] = {"file": value, "hash": file_hash}
            # test if value is another dictionary, run recursive function
            elif isinstance(value, dict):
                new_dict[key] = self._hash_files_in_dict(value)
            # or if the value is a list, then hash each file in the list
            elif isinstance(value, list):
                io_dict[key] = value.copy()  # make a copy of the list so we don't override the original dict
                for i, v in enumerate(value):
                    if type(v) == str and os.path.isfile(v):  # case when entry is a file
                        # obtain hash for file
                        file_hash = self._hash_file(v)

                        # replace with 'file' dict
                        new_dict[key][i] = {"file": v, "hash": file_hash}
                    elif isinstance(v, dict):  # case when entry is another dict
                        new_dict[key][i] = self._hash_files_in_dict(v)

        # return dictionary
        return new_dict

    def _unhash_files_in_dict(self, hash_dict: Dict, xtype: str = "file") -> Dict:
        """Replaces special 'file' dict with hashes or files.

        This method replaces valid a dict containing the following:

            { "file": file_path, "hash": sha256_hash }

        with the value stored at the 'file' or 'hash' key.

        Parameters
        ----------
        hash_dict: Dict
            Dictionary to replace file dict with 'file' or 'hash'.
        xtype: str
            type to replace value with

        Returns
        -------
        Dict
            A dictionary with all file dicts replaced.
        """
        new_dict = hash_dict.copy()

        # loop over keys in dictionary
        for key in new_dict:
            # get value at key
            value = new_dict[key]

            # check if value is a dictionary
            if isinstance(value, dict):
                # check if this dictionary has the 'file' and 'hash' keys
                if "file" in value and "hash" in value:
                    # set the new value for the key based on xtype
                    if xtype == "file":
                        new_dict[key] = value["file"]
                    elif xtype == "hash":
                        new_dict[key] = value["hash"]
                    else:
                        raise ValueError("Invalid xtype.")
                else:  # recursive call on sub dictionary
                    new_dict[key] = self._unhash_files_in_dict(value, xtype)
            elif isinstance(value, list):  # check if value is a list
                hash_dict[key] = value.copy()  # make copy of original list, so we don't overwrite it
                for i, v in enumerate(value):  # loop over values in list
                    if isinstance(v, dict):
                        new_dict[key][i] = self._unhash_files_in_dict({"v": v}, xtype)["v"]  # unhash the value

        # return dictionary
        return new_dict

    def _write_io_hash(self, hash_file: str, io_dict: Dict) -> None:
        """Write input/output hash to file.

        Parameters
        ----------
        hash_file: str
            Location of hash file to write to
        io_dict: Dict
            Input Dictionary
        """
        os.makedirs(os.path.dirname(hash_file), exist_ok=True)
        with open(hash_file, "w") as f:
            json.dump(self._hash_files_in_dict(io_dict), f, sort_keys=True, indent=4)

    def _check_io_hash(self, hash_file: str, current_io_dict: Dict) -> bool:
        """Return if current input/output hash matches input dict of stage

        Parameters
        ----------
        hash_file: str
            Location of hash file to compare current input/output dict to.
        current_io_dict: Dict
            Input/Output dictionary to stage.
        """
        # get hashes for current io dict
        current_hash_dict = self._hash_files_in_dict(current_io_dict)
        # check if hash_file exists
        if os.path.exists(hash_file):
            try:
                with open(hash_file, "r") as f:
                    io_hash_from_file = self._unhash_files_in_dict(json.load(f), "hash")
                    return io_hash_from_file == self._unhash_files_in_dict(current_hash_dict, "hash")
            except json.JSONDecodeError:  # corrupted JSON
                return False
        else:  # No hash file exists at location
            return False

    @staticmethod
    def _write_stage_hash(hash_file: str, stage_bytes: bytes) -> None:
        """Writes stage hash to file

        Parameters
        ----------
        hash_file: str
            Location of hash file to write to
        stage_bytes: bytes
            Byte value of stage function
        """
        os.makedirs(os.path.dirname(hash_file), exist_ok=True)
        with open(hash_file, "wb") as f:
            f.write(stage_bytes)

    @staticmethod
    def _check_stage_hash(hash_file: str, current_stage_bytes: bytes) -> bool:
        """Return True/False if current stage hash matches current stage bytes

        Parameters
        ----------
        hash_file: str
            Location of hash file to compare current stage bytes to
        current_stage_bytes: bytes
            Byte value of stage function to call
        """
        # check if hash_file exists
        if os.path.exists(hash_file):
            # compare the hash file
            with open(hash_file, "rb") as f:
                stage_hash_from_file = f.read()
                return stage_hash_from_file == current_stage_bytes
        else:  # No hash file exists at location
            return False

    @staticmethod
    def _hash_file(filename: str) -> str:
        """Hash file

        Parameters
        ----------
        filename: str
            Filename to hash.

        Returns
        -------
        str
            Hash of file.
        """
        # initialize sha256 hasher
        hasher = hashlib.sha256()

        # open file and hash
        with open(filename, "rb") as f:
            hasher.update(f.read())

        # return the hash
        return hasher.hexdigest()

    @property
    def _get_function_byte_code(self) -> bytes:
        """Get bytes of from function code object for hashing."""
        return get_func_hash(self.function_to_call)

    @property
    def inputs(self) -> List[str]:
        """List[str]: A list of input argument names for the stage."""
        return self.stage_inputs

    @property
    def outputs(self) -> List[str]:
        """List[str]: A list of output argument names for the stage."""
        return self.stage_outputs

    @property
    def args(self) -> Dict:
        """Dict: A dictionary of only the provided input arguments to the
        stage on construction."""
        return self.stage_args

    @property
    def input_args(self) -> Dict:
        """Dict: A dictionary of all input arguments to the stage. Is only
        populated after the `run` method is invoked."""
        return self.stage_input_args

    @property
    def results(self) -> Dict:
        """Dict: A dictionary of the output return values for the stage."""
        return self.stage_results

    @property
    def state(self) -> bool:
        """bool: A flag that specifies whether the current stage has been run
        (The callable has executed)."""
        return self.stage_has_run


def get_modules(methods_list: List[str], top_module: ModuleType) -> List[Tuple[int, ModuleType]]:
    """Recursive function that grabs all valid modules from the methods_list

    Parameters
    ----------
    methods_list: List[str]
        List of strings containing method/module names
    top_module: ModuleType
        A top level module that methods_list should search in

    Returns
    -------
    Tuple[int, ModuleType]
        List of modules and their index in the methods_list
    """
    # add modules to modules list if a module
    modules = list()
    for i, m in enumerate(methods_list):
        try:
            # try getting module
            loaded_module = getattr(top_module, m)
            # module was loaded, so add it to list
            modules.append((i, loaded_module))
        except AttributeError:  # m is not a submodule
            pass

    # recusively search for modules using found modules as top level if they were found
    if len(modules) != 0:
        # create list to store submodules
        submodules = list()
        for index, module in modules:
            # we only need to add modules past index, since a submodule can only be loaded
            # if the top level was loaded first
            try:
                # get the submodules for this toplevel module
                toplevel_submodules = get_modules(methods_list[index + 1 :], module)
                # we need to add index + 1 to the indices of the submodules
                # to get the proper index of the submodule in the original methods_list
                toplevel_submodules = [(index + 1 + n, submod) for n, submod in toplevel_submodules]
                # extend the submodules list
                submodules.extend(toplevel_submodules)
            except IndexError:  # hit end of methods_list
                break
        # now add all submodules to the modules list
        modules.extend(submodules)

    # sort modules by index
    modules.sort(key=lambda x: x[0])

    # return the found modules list
    return modules


def get_func_hash(func: Union[Callable, CodeType], module: ModuleType = None) -> bytes:
    """Hashes a function into unique bytes.

    This function grabs relevant bytes from the
    function code object for hashing. It is ordered as
    the following:

        consts, methods, code

    In consts, the doc sting of the code object is removed
    and any embedded code objects are appended to the end
    of bytes array.

    Parameters
    ----------
    func: Union[Callable, CodeType]
        Callable to hash. If inputting a CodeType also give the module that
        this callable is from.
    module: ModuleType, optional
        Module that the func is from,

    Returns
    -------
    bytes
        Unique bytes representing the function.
    """
    # check if function or code object
    if "__code__" in func.__dir__():  # this is a function
        # unwrap the function if any wrappers exist
        func = get_wrapped_callable(func)

        # get the consts, methods and code of the function
        consts = func.__code__.co_consts[1:]  # drop element 1, the doc string
        methods = func.__code__.co_names
        code = func.__code__.co_code

        # get a reference to code object type
        code_object_type = type(func.__code__)

        # get the module that this function is from
        this_module = importlib.import_module(func.__module__)
    else:  # this is a code object
        # get the consts, methods and code of the function
        consts = func.co_consts[1:]  # drop element 1, the doc string
        methods = func.co_names
        code = func.co_code

        # get a reference to code object type
        code_object_type = type(func)

        # get the module that this code object is from
        this_module = module

    # loop through the consts, if another code object exists in
    # it delete it from consts and recursively call this function on it.
    # these types of objects are usually functions defined inside the
    # currently analyzed callable
    filtered_consts = list()
    code_objects = list()
    for c in consts:
        if code_object_type == type(c):  # check if code object
            code_objects.append(get_func_hash(c, this_module))  # record hash
        else:  # add to the new list
            filtered_consts.append(c)

    # now we would like to find other callables that this
    # callable has called

    # find all modules that this function calls
    modules = get_modules(methods, this_module)

    # for each module, test if it is hashable then (check for __memori_hashable__)
    # call get_func_hash if it is hashable
    filtered_methods = list()
    modules_set = set([m[0] for m in modules])
    for i, m in enumerate(methods):
        # if the method is in the modules set, it is a non built-in module
        if i in modules_set:
            # get the module
            module = [t for t in modules if t[0] == i][0][1]

            # if the module is wrapped, unwrap it
            unwrapped_module = get_wrapped_callable(module)
            # check if __memori_hashable exists
            try:
                if unwrapped_module.__memori_hashable__:  # __memori_hashable__ is always a True attribute
                    code_objects.append(get_func_hash(module))
            except AttributeError:
                # not a hashable function, add to filtered_methods
                filtered_methods.append(m)
        else:  # just a python built-in, add it to the filtered_methods
            filtered_methods.append(m)

    # convert back to tuple
    consts = tuple(filtered_consts)
    methods = tuple(filtered_methods)

    # convert to bytes
    consts = str(consts).encode("utf-8")
    methods = str(methods).encode("utf-8")

    # return concatenated bytes
    bytes_list = [consts, methods, code] + code_objects
    return reduce(lambda x, y: x + y, bytes_list)
