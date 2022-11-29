# memori
[![CircleCI](https://circleci.com/gh/vanandrew/memori/tree/main.svg?style=svg)](https://circleci.com/gh/vanandrew/memori/tree/main)
[![Python package](https://github.com/vanandrew/memori/actions/workflows/python-package.yml/badge.svg?branch=main)](https://github.com/vanandrew/memori/actions/workflows/python-package.yml)
[![codecov](https://codecov.io/gh/vanandrew/memori/branch/main/graph/badge.svg?token=DSVJMHTVLE)](https://codecov.io/gh/vanandrew/memori)

A python library for creating memoized data and code for neuroimaging pipelines

## Table of Contents

1. [Installation](#installation)
2. [Command-Line Usage](#command-line-usage)
    1. [`memori`](#memori)
    2. [`pathman`](#pathman)
3. [Python Usage](#python-usage)
    1. [The `Stage` Object](#the-stage-object)
    2. [The `Pipeline` Object](#the-pipeline-object)
    3. [Stage Aliases and Complex Pipelines](#stage-aliases-and-complex-pipelines)
    4. [Hashing external functions](#hashing-external-functions)
    5. [Path Management](#path-management)

## Installation

To install, use `pip`:
```
pip install memori
```
## Command-Line Usage

`memori` can be used to memoize the running of command-line scripts. It is designed
to check the inputs and sha256 integrity of the calling script and determines whether the running of that calling script should be run or not. It accomplishes
this through 3 checks:

1. Check against the stored cache that input arguments are all the same.
2. Check that the sha256 hash of the calling script (and dependents) are the same.
3. (Optional) Check that the desired outputs match the hashes stored in the cache.

If at least one of these conditions is not met, `memori` will re-run the script.

### memori

The main command-line script to use `memori` is simply called `memori` on the command-line:

```bash
memori -h [any command/script here]
```

The above command will let you view the help of the memori script.

To call memori on a script simply add `memori` before the command you want
to call. For example:

```bash
# wrapping echo in memori
memori echo "this echo command has been wrapped in memori"
```

This will call the `echo` command with `memori`. To cache the running of the
command, you need to specify the `-d/--hash_output` flag:

```bash
# same command but with cached run
memori -d /path/to/cache echo 1
# the first call will print 1
memori -d /path/to/cache echo 1
# running this a second time will not print anything to the screen
# since the inputs/command is the same, so execution is skipped!
```

Since memori determines if a calling script has changed through hashing, you
may want to determine script execution if the calling script depends on another
script. This can occur if calling script 1 calls script 2 and changes are made
to script 2. This can be accomplished through the `-c/--dependents` flag.

```bash
# script execution of script1.sh is now sensitive to changes in script2.sh
memori -c script2.sh -d /path/to/cache script1.sh arg0 arg1...
```

If we are expecting certain files to be written from a calling script,
we can inform `memori` of their existence through the `-o/--outputs` flag.
`memori` will re-run the calling script if the files are missing/modified.

```bash
memori -o /path/to/an/expected/output -d /path/to/cache script.sh arg0 arg1...
```

The `-k/--kill` flag can be used to kill the parent process, if the calling
script returns an error code. This can be useful to halt a parent script if
execution has failed.

Use the `--verbose` flag for under the hood logging info!

### pathman

`pathman` is a script that allows for the convenient management of file
path manipulations.

```bash
pathman -h
```

To view the full help.

###

## Python Usage

`memori` uses a directed acyclic graph (DAG) approach to constructing pipelines.
Nodes of the the graph represent a "logical unit of processing" (up to the user
to define) that can be encomposed in a function. The edges of the
graph transfers data between these nodes to create a pipeline.
To represent this `memori` employs the use of the `Stage` and `Pipeline` objects.

### The `Stage` object

A `Stage` is a wrapper around a python function and is the conceptual equivalent
of a node of our graph. A `Stage` object can take input/output from/to other `Stage`
objects, but can also be run in isolation. Here is an example of a `Stage` wrapped
around a python function:

```python
# our example function
def test_function(a, b, c):
    # Do some stuff
    d = a + b
    e = b + c
    
    # and return stuff
    return d, e
```

We can wrap this function in a `Stage` object and run it:
```python
from memori import Stage

# any values a function returns need to be labeled with the `stage_outputs` parameter
my_test_stage = Stage(test_function, stage_outputs=["d", "e"])

# we can run this stage with the run method and store the results
result = my_test_stage.run(1, 2, 3)
# result will return a dictionary containing: {"d": 3, "e": 5}

# running it again with different parameters
result = my_test_stage.run(2, 3, 4)
# result will return a dictionary containing: {"d": 5, "e": 7}
```

Now lets write a 2nd function that can take input from our `test_function`. Note that 
the input arguments for this function should match the key names of the stage outputs 
for the `test_function`.

```python
# new test function with input arguments matching previous stage
# function stage_output names
def test_function2(d, e):
    return d + e

# and wrap this in a Stage
my_test_stage2 = Stage(test_function2, stage_outputs=["f"])

# to run this we just merely need to **results (kwarg unpacking) to pass information
# from my_test_stage to my_test_stage2
result2 = my_test_stage2.run(**results)
# result2 will return a dictionary containing: {"f": 12}

# or running the entire pipeline from the beginning
result2 = my_test_stage2.run(**my_test_stage.run(1, 2, 3))
# result2 will return a dictionary containing: {"f": 8}

# The previous two lines is the equivalent to running
test_function2(**test_function(1, 2, 3))
```

We can create static values in our `Stage` object that ignores inputs from other stages 
that are passed into the `run` method.

```python3
# Stage will take the same params as test_function
# and use them as static values
my_test_stage = Stage(
    test_function,
    stage_outputs=["d", "e"],
    a=1,
    b=2,
    c=3
)

# when we run the stage, we will see that it does not change with the input (2, 3, 4)
result = my_test_stage.run(2, 3, 4)
# result will return a dictionary containing: {"d": 3, "e": 5}
# if static values weren't used this should return {"d": 5, "e": 7}
```

Now we know how to wrap the functions we write into a `Stage` object, but what benefit 
does this provide? The main feature of `memori` is to `memoize` the inputs to each 
stage and recall the outputs if they are the same. This can enable long running 
functions to be skipped if the results are going to be the same!

```python
# To enable memoization feature, we need to add the hash_output 
# parameter when constructing a Stage object. hash_output is 
# just some directory to where the memoization files can be 
# written to.
my_test_stage = Stage(test_function, stage_output=["d", "e"], hash_output="/test/directory")

# run the stage
my_test_stage.run(1, 2, 3)
```
This will write 3 files: `test_function.inputs`, `test_function.stage`, and 
`test_function.outputs` at the location: /test/directory
These 3 files record the important states of the Stage for memoization, after it has
been run.

The `.stage` file contains information about the function that was run.
It contains some rudimentary static analysis to check whether and code
wrapped by a Stage has changed in a way that will affect the result. If it has 
detected this, it will rerun the stage. Note that this file contains binary data
is mostly non-human readable (unlike the `.inputs` and `.outputs` files).

The `.inputs` and `.outputs` files contain information about the inputs and outputs of the stage. These files are simply JSON files and upon opening them in a text editor you should see the following:

`test_function.inputs`
```json
{
    "a": 1,
    "b": 2,
    "c": 3
}
```

`test_function.outputs`
```json
{
    "d": 3,
    "e": 5
}
```

`memori` checks the `.inputs` file on each run to determine if the stage needs to be run (assuming it has also passed the `.stage` file check). If the stage is skipped, the `.outputs` file is used to load the results into the stage.

By default, `memori` uses the name of the function as the name for the hash files. If you
would like to use a different name for these files, you can set the name of the Stage object with
the `stage_name` parameter in the constructor:

```python
# Stage with a custom stage name
Stage(...
    stage_name="my_stage_name"
...)
```

When passing path/file strings between `Stage` objects, `memori` has a special behavior: if it
determines the string to be a valid file on the disk, it will hash it with the SHA256
algorithm. For files, this gives memoization results that can reflect changes in data integrity:

```python
# now we specify the input and output to be files on the disk
file0 = "/Some/file/path"
file1 = "/Some/second/file/path"

# define our simple test_function that outputs a file path
def test_function3(f0):
    # always return file1
    return file1

# Now we wrap it in a stage
my_test_stage3 = Stage(test_function3, stage_outputs=["file1"], hash_output="/test/directory")

# and run the stage with file0 as the input
results3 = my_test_stage3.run(file0)
```
Now if you examine the `test_function3.inputs` and `test_function3.outputs` you will see the following:

`test_function3.inputs`
```json
{
    "file0": {
        "file": "/Some/file/path",
        "hash": "f0e4c2f76c58916ec258f246851bea091d14d4247a2fc3e18694461b1816e13b"
    }
}
```

`test_function3.outputs`
```json
{
    "file1": {
        "file": "/Some/second/file/path",
        "hash": "f91c3b6b3ec826aca3dfaf46d47a32cc627d2ba92e2d63d945fbd98b87b2b002"
    }
}
```

As shown above `memori` replaces a valid file path with a dictionary entry containing the `"file"` and `"hash"` keys. Valid files are compared by hash values rather than path/filename ensuring data integrity.

> **NOTE**: Since `"file"` and `"hash"` are keywords used to hash valid files. These are reserved keywords that should NOT be used when returning an output from a stage using a dictionary. Doing so could lead to catastrophic results!

> **CAUTION**: `memori` uses JSON to memoize and pass information 
> between `Stage` objects. This means that the inputs/outputs of your function MUST be JSON
> serializable or you will get a serialization error. You can
> also get data conversion effects if you don't use the proper
> data types. For example, python always converts a Tuple to a
> List when serializing a dictionary to JSON. This will lead to
> hash check fail each time you run the Stage! Since whenever memori loads the stage
> output data from the `.outputs` file, the Tuple in the code will never match against 
> list it was converted to in the JSON. So take care to
> use only JSON compatible data types (This means None, integers, floats, 
> strings, bools, lists, and dictionaries are the only valid
> input/output data types in `memori`). 
>
> For data that is not JSON serializable, the typical workaround is to save it to a file
> and pass the file location between the `Stage` objects. This also allows you to take
> advantage of the SHA256 file hashing features of `memori`.

### The `Pipeline` object

What happens when you have more complex pipelines? Maybe you have a `Stage`
that needs to provide input to two different `Stage` objects.

This is where the `Pipeline` object comes in. A `Pipeline` is a collection of Stage
objects with their input/output connections defined. A `Pipeline` object represents
the conceptual DAG that was mentioned above.

```python
from memori import Stage, Pipeline

# create some stages (see the last section on Stages for details)
stage0 = Stage(some params go here...)
stage1 = Stage(some params go here...)
stage2 = Stage(some params go here...)
stage3 = Stage(some params go here...)

# Now we create a Pipeline object, a pipeline takes a definition list during construction
# the definition list is a list of tuples specifying the connection between stages
#
# The "start" keyword is a special instruction that the Pipeline object can read
# it specifies that a particular stage has not precedent Stage and should be a Stage
# that is run first in the Pipeline.
p = Pipeline([
    ("start", stage0),  # stage0 takes no input from other stages, so it should run first
    (stage0, stage1),  # stage0 passes it's output to stage1
    (stage0, stage2),  # and also to stage2
    ((stage1, stage2), stage3)  # stage3 needs inputs from stage1 and stage2, so we use a
                                # special tuple-in-tuple so that it can get outputs from both
                                # NOTE: if stage1 and stage2 have stage_outputs with the same
                                # name, the last stage (right-most) stage will have precedence
                                # for it's output
])

# we can run the Pipeline with the run method, and get it's result
result = p.run(some input parameters here...)
```

Running the pipeline has the effect of invoking the run method 
of each `Stage` object individually, and passing the result of the stage onto the
next stage as defined by the `Pipeline` definition passed in during `Pipeline`
initialization.

## Stage Aliases and Complex Pipelines

When building a complicated pipleine, sometimes the functions that you write
will have input argument names that are different from the `stage_output` names
that you have defined in a `Stage`. Consider the following example:

```python
def test_function(a, b):
    return a + b

def test_function2(c):
    # this might represent some complicated processing
    c += 1
    return c

def test_function3(d):
    # this might be another function with some more complocated processing
    d += 2
    return d 
```

Now let's say I want to pass the result of `test_function` to both `test_function2` and
`test_function3`. This presents an issue because `test_function2` and `test_function3` have
different input argument names. So if I define the `stage_output` of the wrapped `test_function`
to be `stage_outputs=["c"]` this won't work for `test_function3` and if I define it to be
`stage_outputs=["d"]` it won't work for `test_function2`.

One way of solving this issue would be to rewrite the `test_function2` and `test_function3`
functions to have the same argument name, this may not always be possible (particularly when
wrapping a function call from a third-party library). Another option would be to wrap the
call of either `test_function2` or `test_function3` to take in the same input. For example:

```python3
# this is necessary hashing external function calls
# more about the hashable wrapper in the next section
from memori import hashable

# we wrap the call of test_function3
def test_function3_mod(c):
    return hashable(test_function3)(c)
```

Now when we create the `Stage` for each function, `test_function2` and `test_function3_mod` now have the same input argument names and can take in input from `test_function`.

While this solution works (and indeed this was how it used to be done), `memori` provides a more 
convienent solution through Stage aliases. Aliases can map the name of one of the stage outputs to 
another name. When creating a `Stage` object, you can define this through the `aliases` parameter.

```python
# We wrap test_function in a Stage, and specify an alias from d -> c
test_stage = Stage(test_function, stage_outputs=["c"], aliases=["d": "c"])

# Now I can construct stages around test_function2 and test_function3 without
# writing extra code
test_stage2 = Stage(test_function2, stage_outputs=["e"])
test_stage3 = Stage(test_function3, stage_outputs=["f"])

# now definte the pipeline
my_pipeline = Pipeline(
    [
        ("start", test_stage),
        (test_stage, test_stage2),
        (test_stage, test_stage3), # because we mapped d -> c, memori know where to pass the result to
    ]
)
```

Stage aliases reduces the need for extra boilerplate code, and adding on an extra
stage the feeds from `test_stage` is as simple as adding another alias.

## Hashing external functions

In the last section, we saw the use of the hashable wrapper when trying to wrap a
function call in another function. But what does it actually do? Consider the
following example:

```python
def test_function(a, b)
    c = a + b
    d = test_function2(c)
    return d

def test_function2(c)
    return c + 1

stage0 = Stage(test_function, stage_outputs=["d"], hash_output="test")
result = stage0.run(1, 2)
# this will return the result {"d": 4}
```

Now, what if we change the code of test_function to:

```python
# change up test_function!
def test_function(a, b)
    c = a + b + 1
    d = test_function2(c)
    return d
```

Rebuilding the stage on this function and invoking the `run` method it will cause the
`.stage` hash to mismatch (since the function signature is different with the added
`+ 1` in the code), and the function will rerun instead of loading from cache
(this should return the result `{"d": 5}`).

So the function hashing feature of memori works! but what happens when we modify
`test_function2` and rerun our stage.

```python
# will memori see this change?
def test_function2(c):
    return c + 2
```

Rerunning the stage with the updated `test_function2`, you will see that after invoking
`run`, the `Stage` object simply loads the result from the `.output` file and ignores
the difference in the updated `test_function2` (this will still return `{"d": 5}` rather
than `{"d": 6}`.

This occurs because `memori` function hashing only occurs one call deep. Meaning that
only the instructions of the wrapped callable are the only thing that is hashed. Function calls inside a function are simply recorded as constants, meaning that only
the name `test_function2` is memoized, not the actual instructions!

To correct this issue, `memori` provides the `hashable` wrapper. This wrapper marks 
a function so that memori knows to try and hash it.

```python
# wrap test_funtion2 in hashable
def test_function(a, b)
    c = a + b + 1
    d = hashable(test_function2)(c)
    return d
```

Alternatively, you can add the hashable wrapper a decorator.

```python
# this is the same as calling hashable(test_function2)
# but makes everything transparent
@hashable
def test_function2(c)
    return c + 1
```

This allows you to simply call `test_function2` without worrying about calling
the hashable wrapper each time.

## Path Management

`memori` also provides a path management utility called `PathManager`. It
is useful for manipulating file paths as well as suffixes and extensions.
If is derived from a `Path` object from the [pathlib](https://docs.python.org/3/library/pathlib.html) library, and so can use any of the
parent methods as well.

Here are a few useful examples:

```python
from memori import PathManager as PathMan

# a string to a path I want PathManager to manage
my_file_path_pm = PathMan("/my/path/to/a/file.ext.ext2")

# get only the file prefix
prefix = my_file_path_pm.get_prefix()
# prefix contains "file"

# get the path and file prefix
path_and_prefix = my_file_path_pm.get_path_and_prefix()
# path_and_prefix contains "/my/path/to/a/file"

# change path of the file, keeping the filename the same
repathed = my_file_path_pm.repath("/new/path")
# repathed contains "/new/path/file.ext.ext2"

# append a suffix (following the BIDS standard, suffixes should always have _)
suffixed = my_file_path_pm.append_suffix("_newsuffix")
# suffixed contains "/my/path/to/a/file_newsuffix.ext.ext2"

# replace last suffix
replaced = suffixed.replace_suffix("_newsuffix2")
# replaced contains "/my/path/to/a/file_newsuffix2.ext.ext2"

# delete last suffix
deleted = replaced.delete_suffix()
# deleted contains "/my/path/to/a/file.ext.ext2"

# methods can be chained together
chained = my_file_path_pm.repath("/new").append_suffix("_test").get_path_and_prefix()
# chained contains /new/file_test

# return as a string
my_file_path = my_file_path_pm.path
# /new/file_test
```
