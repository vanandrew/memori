import os
import sys
import tempfile
import json
import importlib
from pathlib import Path
from memori import Pipeline, Stage, redefine_result_key
from memori.stage import get_func_hash
from memori.helpers import *


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

    # wrap function in a stage
    stage0 = Stage(func, stage_outputs=["z"])

    # check stage inputs/outputs
    assert stage0.inputs == ["x", "y"]
    assert stage0.outputs == ["z"]

    # check args
    assert stage0.args == {}

    # run stage
    stage0.run(1, 2)
    assert stage0.input_args == {"x": 1, "y": 2}
    assert stage0.results == {"z": 3}
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
                stage3 = Stage(func, stage_outputs=["z"], hash_output=d)
                assert stage3.run(1, 2) == {"z": 3}

                # run again, this should load results from cache
                assert stage3.run(1, 2) == {"z": 3}

                # should be new results
                assert stage3.run(1, 3) == {"z": 4}

                # should be wrong results, due to force loading info from cache
                assert stage3.run(1, 2, force_skip_stage=True) == {"z": 4}

                # should be correct results
                assert stage3.run(1, 2) == {"z": 3}

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


def test_pipeline():
    def func0(x, y):
        return x + y

    def func1(z, a):
        return z * a

    def func2(z, b):
        return z * b

    def func3(b, c, d):
        return (b + c + d, b * c * d)

    def func4(b, c, d):
        return (b + c + d, b * c * d)

    def func5(b, c, d=1):
        return 1

    def func6(b, c, d):
        return 1

    def func7(filename="test"):
        return filename

    with tempfile.TemporaryDirectory() as d:
        # define stages
        stage0 = Stage(func0, stage_outputs=["z"], hash_output=d)
        stage1 = Stage(func1, a=2, stage_outputs=["b"], hash_output=d)
        stage2 = Stage(func2, stage_outputs=["c"], hash_output=d)
        stage3 = Stage(func3, d=2, stage_outputs=["e", "f"], hash_output=d)

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
    test_file = """
from memori.helpers import hashable

@hashable
def test_func(a, b):
    return a + b

@hashable
def test_func2(a, b):
    return test_func(a, b) + 1
"""

    test_file2 = """
from memori.helpers import hashable

@hashable
def test_func(a, b):
    return a + b - 1

@hashable
def test_func2(a, b):
    return test_func(a, b) + 1
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
                f.write(test_file)

            # append d to sys.path
            sys.path.append(d)

            # load the module
            module = importlib.import_module(module_name + ".funcs")

            # hash the test_func2 function
            hash0 = get_func_hash(module.test_func2)

            # write a new test file to directory
            # write test file to directory
            with open(os.path.join(mod, "funcs.py"), "w") as f:
                f.write(test_file2)

            # reload the module
            module = importlib.reload(module)

            # hash the test_func2 function
            hash1 = get_func_hash(module.test_func2)

            # hashes should be different
            assert hash0 != hash1


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


def test_create_symlink_to_folder():
    # Create temp dir to teset output path
    with tempfile.TemporaryDirectory() as d:
        with tempfile.TemporaryDirectory() as d2:
            symlink = create_symlink_to_folder(Path(d), Path(d2), "test_link")
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
