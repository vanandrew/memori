from ast import Break
import os
import sys
import tempfile
import json
import importlib
import logging
import pytest
from pathlib import Path
from memori import Pipeline, Stage, redefine_result_key
from memori.stage import get_func_hash
from memori.helpers import (
    hashable,
    get_wrapped_callable,
    create_output_path,
    use_abspaths,
    create_symlinks_to_input_files,
    create_symlink_to_path,
    create_symlink_to_folder,
    working_directory,
    use_output_path_working_directory,
    script_to_python_func,
)
from memori.pathman import (
    delete_suffix,
    get_prefix,
    get_path_and_prefix,
    append_suffix,
    replace_suffix,
    delete_suffix,
    repath,
    PathManager,
)

# set logging to INFO level
logging.basicConfig(level=logging.INFO)


def test_stage():
    # create a function
    def func(x, y):
        def sum(a, b):
            return a + b

        return sum(x, y)

    # create another function
    def func2(a="test"):
        return a

    # create a third function
    def func3(a, b):
        return [
            [a, b, 1],
        ]

    # create a fourth function
    def func4(a, b):
        return a, {"some_key": b}, [{"some_key2": a, "some_key3": b}]

    # wrap function in a stage
    stage0 = Stage(func)

    # check stage inputs/outputs
    assert stage0.inputs == ["x", "y"]
    assert stage0.outputs == ["output"]

    # check args
    assert stage0.args == {}

    # run stage
    stage0.run(1, 2)
    assert stage0.input_args == {"x": 1, "y": 2}
    assert stage0.results == {"output": 3}
    assert stage0.state

    # test override stage arguments
    stage1 = Stage(func, x=2, stage_outputs=["z"])
    stage1.run(1, 2)
    assert stage1.results == {"z": 4}
    stage2 = Stage(func, x=4, y=5, stage_outputs=["z"])
    stage2.run()
    assert stage2.results == {"z": 9}
    assert stage2.args == {"x": 4, "y": 5}

    # test stage hashing
    with tempfile.TemporaryDirectory() as d:
        with tempfile.NamedTemporaryFile() as f:
            with tempfile.NamedTemporaryFile() as f2:
                # initial run
                stage3 = Stage(func, stage_outputs=["z"], hash_output=d, aliases={"test": "z"})
                assert stage3.run(1, 2) == {"z": 3}

                # test aliased result
                assert stage3.results == {"z": 3, "test": 3}
                stage3.stage_aliases["test2"] = "z"
                del stage3.stage_aliases["test"]
                assert stage3.results == {"z": 3, "test2": 3}
                del stage3.stage_aliases["test2"]
                assert stage3.results == {"z": 3}

                # run again, this should load results from cache
                assert stage3.run(1, 2) == {"z": 3}

                # should be new results
                assert stage3.run(1, 3) == {"z": 4}

                # should be wrong results, due to force loading info from cache
                assert stage3.run(1, 2, force_skip_stage=True) == {"z": 4}

                # should be correct results
                assert stage3.run(1, 2) == {"z": 3}

                # this should rerun the stage due to adding different stage_outputs
                stage3 = Stage(func, stage_outputs=["z2"], hash_output=d)
                assert stage3.run(1, 2) == {"z2": 3}
                assert not stage3.stage_from_hash
                assert stage3.run(1, 2) == {"z2": 3}
                assert stage3.stage_from_hash

                # return to original state
                stage3 = Stage(func, stage_outputs=["z"], hash_output=d, aliases={"test": "z"})
                assert stage3.run(1, 2) == {"z": 3}

                # test stage hashing with different location
                with tempfile.TemporaryDirectory() as d2:
                    stage3.hash_output = d2
                    assert stage3.run(1, 2) == {"z": 3}
                    assert os.path.isfile(os.path.join(d2, "func.inputs"))
                    assert os.path.isfile(os.path.join(d2, "func.stage"))
                    assert os.path.isfile(os.path.join(d2, "func.outputs"))
                    # test changing stage argument
                    stage3.set_stage_arg("x", 3)
                    assert stage3.run(1, 2) == {"z": 5}
                    stage3.set_stage_arg("y", 4)
                    assert stage3.run(1, 2) == {"z": 7}
                    # this should fail
                    with pytest.raises(ValueError):
                        stage3.set_stage_arg("z", 3)

                # delete the set stage args
                for arg in stage3.stage_inputs:
                    stage3.del_stage_arg(arg)
                # this should fail
                with pytest.raises(ValueError):
                    stage3.del_stage_arg("z")
                # this should also fail
                with pytest.raises(KeyError):
                    stage3.del_stage_arg("x")

                # return stage hash to original location
                stage3.hash_output = d

                # test file hashing
                stage4 = Stage(func2, stage_outputs=["a"], hash_output=d)
                assert stage4.run(f.name) == {"a": f.name}
                with open(os.path.join(d, "func2.inputs")) as hash_file:
                    input_dict = json.load(hash_file)
                    assert "hash" in input_dict["a"] and "file" in input_dict["a"]
                with open(os.path.join(d, "func2.outputs")) as hash_file:
                    output_dict = json.load(hash_file)
                    assert "hash" in output_dict["a"] and "file" in output_dict["a"]

                # rerun stage4 with outputs from hash
                assert stage4.run(f.name) == {"a": f.name}

                # test force running and writing
                assert stage3.run(1, 3, force_run_stage=True, force_hash_write=True) == {"z": 4}

                # test list hashing
                stage5 = Stage(func3, stage_outputs=["a"], hash_output=d)
                results = stage5.run(f.name, f2.name)
                assert results == {"a": [f.name, f2.name, 1]}
                with open(os.path.join(d, "func3.inputs")) as hash_file:
                    input_dict = json.load(hash_file)
                    assert "hash" in input_dict["a"] and "file" in input_dict["a"]
                    assert "hash" in input_dict["b"] and "file" in input_dict["b"]
                with open(os.path.join(d, "func3.outputs")) as hash_file:
                    output_dict = json.load(hash_file)
                    assert "hash" in output_dict["a"][0] and "file" in output_dict["a"][0]
                    assert "hash" in output_dict["a"][1] and "file" in output_dict["a"][1]

                # test dict hashiing
                stage6 = Stage(func4, stage_outputs=["a", "b", "c"], hash_output=d)
                results = stage6.run(f.name, f2.name)
                assert results == {
                    "a": f.name,
                    "b": {"some_key": f2.name},
                    "c": [{"some_key2": f.name, "some_key3": f2.name}],
                }
                with open(os.path.join(d, "func4.inputs")) as hash_file:
                    input_dict = json.load(hash_file)
                    assert "hash" in input_dict["a"] and "file" in input_dict["a"]
                    assert "hash" in input_dict["b"] and "file" in input_dict["b"]
                with open(os.path.join(d, "func4.outputs")) as hash_file:
                    output_dict = json.load(hash_file)
                    assert "hash" in output_dict["a"] and "file" in output_dict["a"]
                    assert "hash" in output_dict["b"]["some_key"] and "file" in output_dict["b"]["some_key"]
                    assert "hash" in output_dict["c"][0]["some_key2"] and "file" in output_dict["c"][0]["some_key2"]
                    assert "hash" in output_dict["c"][0]["some_key3"] and "file" in output_dict["c"][0]["some_key3"]
                # load from hash output
                assert results == stage6.run(f.name, f2.name)


def test_pipeline():
    def func0(x, y):
        return x + y

    def func1(z, a):
        return z * a

    def func2(z, b):
        return z * b

    def func3(b, c, d):
        return (b + c + d, b * c * d)

    def func3_mod(b, c2, d):
        return (b + c2 + d, b * c2 * d)

    def func4(b, c, d):
        return (b + c + d, b * c * d)

    def func5(b, c, d=1):
        return 1

    def func6(b, c, d):
        return 1

    def func7(filename="test"):
        return filename

    def func8(filenames=["test", "test2"]):
        return filenames[0], filenames[1]

    with tempfile.TemporaryDirectory() as d:
        # define stages
        stage0 = Stage(func0, stage_outputs=["z"], hash_output=d)
        stage1 = Stage(func1, a=2, stage_outputs=["b"], hash_output=d)
        stage2 = Stage(func2, stage_outputs=["c"], hash_output=d, aliases={"c2": "c"})
        stage3 = Stage(func3, d=2, stage_outputs=["e", "f"], hash_output=d)
        stage3_mod = Stage(func3_mod, d=2, stage_outputs=["e", "f"], hash_output=d)

        # create a pipeline
        pipeline0 = Pipeline(
            [("start", stage0), (stage0, stage1), ((stage0, stage1), stage2), ((stage1, stage2), stage3)]
        )

        # run the pipeline
        pipeline0.run(1, 2)

        # get results
        assert pipeline0.results == {"z": 3, "b": 6, "c": 18, "e": 26, "f": 216}

        # test cached results (all tuples are converted to lists)
        assert pipeline0.run(1, 2) == {"z": 3, "b": 6, "c": 18, "e": 26, "f": 216}

        # test with aliased stage output key
        pipeline0_mod = Pipeline(
            [("start", stage0), (stage0, stage1), ((stage0, stage1), stage2), ((stage1, stage2), stage3_mod)]
        )
        assert pipeline0_mod.run(1, 2) == {"z": 3, "b": 6, "c": 18, "e": 26, "f": 216}
        assert stage2.results == {"c": 18, "c2": 18}

        # test with new stage
        stage4 = Stage(func4, d=1, stage_outputs=["e", "f"], hash_output=d)
        pipeline1 = Pipeline(
            [("start", stage0), (stage0, stage1), ((stage0, stage1), stage2), ((stage1, stage2), stage4)]
        )
        assert pipeline1.run(1, 2) == {"z": 3, "b": 6, "c": 18, "e": 25, "f": 108}

        # test with keyword argument in function
        stage5 = Stage(func5, stage_outputs=["e"], hash_output=d)
        pipeline2 = Pipeline(
            [("start", stage0), (stage0, stage1), ((stage0, stage1), stage2), ((stage1, stage2), stage5)]
        )
        assert pipeline2.run(1, 2) == {"z": 3, "b": 6, "c": 18, "e": 1}

        # test with argument exception
        stage6 = Stage(func6, stage_outputs=["e"], hash_output=d)
        pipeline3 = Pipeline(
            [("start", stage0), (stage0, stage1), ((stage0, stage1), stage2), ((stage1, stage2), stage6)]
        )
        try:
            pipeline3.run(1, 2)
        except TypeError:
            pass

        # test with file
        with tempfile.NamedTemporaryFile() as f:
            stage7 = Stage(func7, stage_outputs=["filename"], hash_output=d)
            pipeline4 = Pipeline([("start", stage7)])
            pipeline4.run(filename=f.name)
            assert os.path.isfile(pipeline4.results["filename"])

        # test with two files
        with tempfile.NamedTemporaryFile() as f1:
            with tempfile.NamedTemporaryFile() as f2:
                stage8 = Stage(func8, stage_outputs=["filename", "filename2"], hash_output=d)
                pipeline5 = Pipeline([("start", stage8)])
                pipeline5.run(filenames=[f1.name, f2.name])
                assert os.path.isfile(pipeline5.results["filename"])
                assert os.path.isfile(pipeline5.results["filename2"])
                # run again
                pipeline5.run(filenames=[f1.name, f2.name + "abc"])
                assert os.path.isfile(pipeline5.results["filename"])
                assert not os.path.isfile(pipeline5.results["filename2"])

        # test stage type checking
        try:
            Pipeline([("invalid_string", lambda x: x)])
        except ValueError:
            pass


def test_redefine_result_key():
    dictionary = {"hello": 1, "test": 2}
    new_dict = redefine_result_key(dictionary, "hello", "testing")
    assert new_dict == {"testing": 1, "test": 2}


def test_hashable():
    test_file0 = """
from memori.helpers import hashable
import math
import os

@hashable
def test_func(a, b):
    print(os.path.join("hi", "hi2"))
    return a + b

def no_hash(a):
    return a + 1

@hashable
def test_func2(a, b):
    return test_func(a, b) + no_hash(1) + math.floor(2.5)
"""

    test_file1 = """
from memori.helpers import hashable
import math
import os

@hashable
def test_func(a, b):
    print(os.path.join("hi", "hi2"))
    return a + b - 1

def no_hash(a):
    return a + 2

@hashable
def test_func2(a, b):
    return test_func(a, b) + no_hash(1) + math.floor(2.5)
"""

    test_file2 = """
from memori.helpers import hashable

@hashable
class TestClass:
    def __init__(self):
        self.a = 1

    def test_method(self):
        return self.a + 1

    @property
    def test_prop(self):
        return 1

    @test_prop.setter
    def test_prop(self, value):
        pass

    @test_prop.deleter
    def test_prop(self):
        pass

    class TestClass2:
        def __init__(self):
            self.a = 1

        def test_method(self):
            return self.a + 1

@hashable
def test_func(a, b):
    tc = TestClass()
    return tc.test_method() + no_hash(5)
"""

    test_file3 = """
from memori.helpers import hashable

@hashable
class TestClass:
    def __init__(self):
        self.a = 1

    def test_method(self):
        return self.a + 2

    @property
    def test_prop(self):
        return 1

    @test_prop.setter
    def test_prop(self, value):
        pass

    @test_prop.deleter
    def test_prop(self):
        pass

    class TestClass2:
        def __init__(self):
            self.a = 1

        def test_method(self):
            return self.a + 1

@hashable
def test_func(a, b):
    tc = TestClass()
    return tc.test_method() + no_hash(7)
"""

    test_file4 = """
def test_func(a, b):
    return a + b
"""

    with tempfile.TemporaryDirectory() as d:
        with tempfile.TemporaryDirectory(dir=d) as mod:
            # get module name
            module_name = os.path.basename(mod)

            # create init.py at module directory
            with open(os.path.join(mod, "init.py"), "w") as f:
                pass

            # write test file to directory
            with open(os.path.join(mod, "funcs.py"), "w") as f:
                f.write(test_file0)

            # append d to sys.path
            sys.path.append(d)

            # load the module
            module = importlib.import_module(module_name + ".funcs")

            # hash the test_func2 function
            hash0 = get_func_hash(module.test_func2)

            # write a new test file to directory
            # write test file to directory
            with open(os.path.join(mod, "funcs.py"), "w") as f:
                f.write(test_file1)

            # reload the module
            module = importlib.reload(module)

            # hash the test_func2 function
            hash1 = get_func_hash(module.test_func2)

            # hashes should be different
            assert hash0 != hash1

    with tempfile.TemporaryDirectory() as d:
        with tempfile.TemporaryDirectory(dir=d) as mod:
            # get module name
            module_name = os.path.basename(mod)

            # create init.py at module directory
            with open(os.path.join(mod, "init.py"), "w") as f:
                pass

            # write test file to directory
            with open(os.path.join(mod, "funcs.py"), "w") as f:
                f.write(test_file2)

            # append d to sys.path
            sys.path.append(d)

            # load the module
            module = importlib.import_module(module_name + ".funcs")

            # hash the test_func2 function
            hash2 = get_func_hash(module.test_func)

    with tempfile.TemporaryDirectory() as d:
        with tempfile.TemporaryDirectory(dir=d) as mod:
            # get module name
            module_name = os.path.basename(mod)

            # create init.py at module directory
            with open(os.path.join(mod, "init.py"), "w") as f:
                pass

            # write test file to directory
            with open(os.path.join(mod, "funcs.py"), "w") as f:
                f.write(test_file3)

            # append d to sys.path
            sys.path.append(d)

            # load the module
            module = importlib.import_module(module_name + ".funcs")

            # hash the test_func2 function
            hash3 = get_func_hash(module.test_func)

    assert hash2 != hash3

    with tempfile.TemporaryDirectory() as d:
        with tempfile.TemporaryDirectory(dir=d) as mod:
            # get module name
            module_name = os.path.basename(mod)

            # create init.py at module directory
            with open(os.path.join(mod, "init.py"), "w") as f:
                pass

            # write test file to directory
            with open(os.path.join(mod, "funcs.py"), "w") as f:
                f.write(test_file4)

            # append d to sys.path
            sys.path.append(d)

            # load the module
            module = importlib.import_module(module_name + ".funcs")

            # get the test_func function
            test_func = module.test_func

            # define a new function
            def test_func2(a, b):
                return hashable(test_func)(a, b) + 1

            # run in stage
            stage = Stage(test_func2, stage_outputs=["c"], hash_output=d)
            stage.run(1, 2)
            assert not stage.stage_from_hash
            stage.run(1, 2)
            assert stage.stage_from_hash


def test_get_wrapped_callable():
    @create_output_path
    def test_function_with_decorator(output_path, test_arg1, test_arg2):
        return output_path, test_arg1, test_arg2

    test_function = get_wrapped_callable(test_function_with_decorator)
    assert test_function.__code__.co_varnames == ("output_path", "test_arg1", "test_arg2")


def test_create_output_path():
    # This function should fail
    try:

        @create_output_path
        def fail_function(test):
            return test

        fail_function(None)
    except ValueError:
        pass

    # This function should pass
    @create_output_path
    def pass_function(output_path, test):
        return output_path, test

    # Create temp dir to teset output path
    with tempfile.TemporaryDirectory() as d:
        test_path = os.path.join(d, "test_path")
        pass_function(test_path, 1)
        assert os.path.exists(test_path)


def test_use_abspaths():
    current_dir = os.getcwd()
    with tempfile.NamedTemporaryFile() as f:
        rel_f = os.path.relpath(f.name, current_dir)

        @use_abspaths
        def test_function(test, test2, test3="/test", test4=0):
            return test, test2, test3, test4

        abs_f1, num1, abs_f2, num2 = test_function(rel_f, 1, test3=rel_f, test4=2)
        assert abs_f1 == f.name
        assert num1 == 1
        assert abs_f2 == f.name
        assert num2 == 2


def test_create_symlinks_to_input_files():
    with tempfile.TemporaryDirectory() as d:
        temp_path = os.path.join(d, "input_path")

        @create_symlinks_to_input_files(symlink_dir=temp_path)
        def test_function(arg1, arg2, arg3="", arg4=0):
            return arg1, arg2, arg3, arg4

        with tempfile.NamedTemporaryFile() as f1:
            with tempfile.NamedTemporaryFile() as f2:
                f1_basename = os.path.basename(f1.name)
                f2_basename = os.path.basename(f2.name)
                abs_f1, num1, abs_f2, num2 = test_function(f1.name, 1, arg3=f2.name, arg4=2)
                correct_outputs = (os.path.join(temp_path, f1_basename), os.path.join(temp_path, f2_basename))
                assert (abs_f1, abs_f2) == correct_outputs
                assert (num1, num2) == (1, 2)
                # test removal of original symlink
                test_function(f1.name, 1, arg3=f2.name, arg4=2)


def test_create_symlink_to_path():
    # Create temp dir to teset output path
    with tempfile.TemporaryDirectory() as d:
        with tempfile.NamedTemporaryFile() as f:
            symlink = create_symlink_to_path(f.name, d)
            assert os.path.islink(symlink)
            assert os.path.realpath(symlink) == f.name

            # test recreating symlink
            symlink = create_symlink_to_path(f.name, d)
            assert os.path.islink(symlink)
            assert os.path.realpath(symlink) == f.name

            # test when a file already exists at the symlink location
            os.unlink(symlink)
            Path(symlink).touch()
            symlink = create_symlink_to_path(f.name, d)
            assert os.path.islink(symlink)
            assert os.path.realpath(symlink) == f.name


def test_create_symlink_to_folder():
    # Create temp dir to teset output path
    with tempfile.TemporaryDirectory() as d:
        with tempfile.TemporaryDirectory() as d2:
            symlink = create_symlink_to_folder(Path(d), Path(d2), "test_link")
            assert os.path.islink(symlink)
            assert symlink.resolve() == Path(d)

            # test recreating symlink
            symlink = create_symlink_to_folder(Path(d), Path(d2), "test_link")
            assert os.path.islink(symlink)
            assert symlink.resolve() == Path(d)

            # test when a file already exists at the symlink location
            Path(os.path.join(d2, "test_link2")).touch()
            symlink = create_symlink_to_folder(Path(d), Path(d2), "test_link2")
            assert os.path.islink(symlink)
            assert symlink.resolve() == Path(d)


def test_working_directory():
    # get current directory
    cwd = os.getcwd()
    # Create temp dir to teset output path
    with tempfile.TemporaryDirectory() as d1:
        with tempfile.TemporaryDirectory() as d2:
            # in d2
            with working_directory(d2):
                assert os.path.abspath(os.getcwd()) == os.path.abspath(d2)
            # exit d2
        # in d1
        with working_directory(d1):
            assert os.path.abspath(os.getcwd()) == os.path.abspath(d1)
        # exit d1
    # in orig
    assert os.path.abspath(os.getcwd()) == os.path.abspath(cwd)


def test_use_output_path_working_directory():
    # create temp dir
    with tempfile.TemporaryDirectory() as d:

        @use_output_path_working_directory
        def test_function(output_path):  # pylint: disable=unused-argument
            current_dir = os.getcwd()
            return current_dir

        def test_function2(output_path):  # pylint: disable=unused-argument
            current_dir = os.getcwd()
            return current_dir

        directory = test_function(d)
        directory2 = test_function2(d)
        assert directory == d
        assert directory2 != d


def test_get_prefix():
    test_path = "/test0/test1/test2.nii.gz"
    assert get_prefix(test_path) == "test2"
    assert PathManager(test_path).get_prefix().path == "test2"


def test_get_path_and_prefix():
    test_path = "/test0/test1/test2.nii.gz"
    assert get_path_and_prefix(test_path) == "/test0/test1/test2"
    assert PathManager(test_path).get_path_and_prefix().path == "/test0/test1/test2"


def test_append_suffix():
    test_path = "/test0/test1/test2.nii.gz"
    assert append_suffix(test_path, "_test3") == "/test0/test1/test2_test3.nii.gz"
    assert PathManager(test_path).append_suffix("_test3").path == "/test0/test1/test2_test3.nii.gz"


def test_replace_suffix():
    test_path = "/test0/test1_test2"
    assert replace_suffix(test_path, "_test3") == "/test0/test1_test3"
    assert PathManager(test_path).replace_suffix("_test3").path == "/test0/test1_test3"


def test_delete_suffux():
    test_path = "/test0/test1_test2"
    assert delete_suffix(test_path) == "/test0/test1"
    assert PathManager(test_path).delete_suffix().path == "/test0/test1"


def test_repath():
    test_path = "/test0/test1/test2"
    assert repath("/test4/test5", test_path) == "/test4/test5/test2"
    assert PathManager(test_path).repath("/test4/test5").path == "/test4/test5/test2"


def test_script_to_python_func():
    with tempfile.TemporaryDirectory() as tmp_dir:
        with tempfile.NamedTemporaryFile() as tmp_file:
            script_path = os.path.join(tmp_dir, "script.sh")
            with open(script_path, "w") as f:
                f.write("#!/bin/bash\necho 'hello world'")
            os.chmod(script_path, 0o777)

            test_func = script_to_python_func(script_path, 0, tmp_file.name)
            assert {"output": 0, "output0": tmp_file.name} == Stage(
                test_func, stage_outputs=["output", "output0"], hash_output=tmp_dir
            ).run()
            assert {"output": 0, "output0": tmp_file.name} == Stage(
                test_func, stage_outputs=["output", "output0"], hash_output=tmp_dir
            ).run()

            with open(script_path, "w") as f:
                f.write("#!/bin/bash\necho $1")
            os.chmod(script_path, 0o777)

            test_func = script_to_python_func(script_path, 1, [tmp_file.name, tmp_file.name])
            assert {"output": 0, "output0": tmp_file.name, "output1": tmp_file.name} == Stage(
                test_func, stage_outputs=["output", "output0", "output1"], hash_output=tmp_dir
            ).run("1")
            assert {"output": 0, "output0": tmp_file.name, "output1": tmp_file.name} == Stage(
                test_func, stage_outputs=["output", "output0", "output1"], hash_output=tmp_dir
            ).run("1")
            try:
                Stage(test_func, hash_output=tmp_dir).run()
            except TypeError:
                pass  # this is expected to fail with a TypeError

            try:  # when script does not exist
                test_func = script_to_python_func([script_path, "/does/not/exist"], 1, [tmp_file.name, tmp_file.name])
            except FileNotFoundError:
                pass


def test_script_memori():
    from memori.scripts.memori import main

    with tempfile.TemporaryDirectory() as tmp_dir:
        with tempfile.NamedTemporaryFile() as f:
            with tempfile.NamedTemporaryFile() as log_file:
                sys.argv = [
                    "memori",
                    "--log_file",
                    log_file.name,
                    "--verbose",
                    "-o",
                    f.name,
                    "-c",
                    "ls",
                    "-d",
                    tmp_dir,
                    "echo",
                    "1",
                ]
                assert main() == 0
                assert main() == 0  # skips execution

                sys.argv = [
                    "memori",
                    "--verbose",
                    "-p",
                    "4",
                    "echo",
                    "--arg0",
                    "1",
                    "--arg_output0",
                    "output0",
                ]
                assert main() == 0

                # this will raise a value error
                sys.argv = [
                    "memori",
                    "-p",
                    "4",
                    "echo",
                ]
                try:
                    main()
                except ValueError:
                    pass

                # this will return a non-zero exit code
                sys.argv = [
                    "memori",
                    "-p",
                    "4",
                    "false",
                    "--arg0",
                    "1",
                ]
                assert main() == 1


def test_script_pathman():
    from memori.scripts.pathman import main

    sys.argv = [
        "pathman",
        "file",
        "test",
    ]

    try:  # except on invalid command
        main()
    except ValueError:
        pass

    sys.argv = [
        "pathman",
        "/path/to/file",
        "get_prefix",
        "append_suffix",
        "_test",
        "replace_suffix",
        "_test2",
        "delete_suffix",
    ]
    main()
