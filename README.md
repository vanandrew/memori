# memori
[![CircleCI](https://circleci.com/gh/vanandrew/memori/tree/main.svg?style=svg)](https://circleci.com/gh/vanandrew/memori/tree/main)
[![Python package](https://github.com/vanandrew/memori/actions/workflows/python-package.yml/badge.svg?branch=main)](https://github.com/vanandrew/memori/actions/workflows/python-package.yml)
[![codecov](https://codecov.io/gh/vanandrew/memori/branch/main/graph/badge.svg?token=DSVJMHTVLE)](https://codecov.io/gh/vanandrew/memori)

A python library for creating memoized data and code for neuroimaging pipelines

## Install

To install, use `pip`:
```
pip install memori
```

## Usage

`memori` uses a directed acyclic graph (DAG) approach to constructing pipelines.
Nodes of the the graph represent a "logical unit of processing" (up to the user
to define) that can be encomposed in a function. The edges of the
graph transfers data between these nodes to create a pipeline.
To represent this `memori` employs the use of the `Stage` and `Pipeline` objects.

### `Stage`

A `Stage` is a wrapper around a python function and is the conceptual equivalent
of a node of our graph. A `Stage` object can take input/output from/to other `Stage`
objects, but can also be run in isolation. Here is an example of a `Stage` wrapped
around a python function:

```
# our example function
def test_function(test_func_var0, test_func_var1, test_func_var2):
    # Do some stuff
    test_func_var3 = test_func_var0 + test_func_var1
    test_func_var4 = test_func_var1 + test_func_var2
    
    # and return stuff
    return test_func_var3, test_func_var4

# we wrap this function in a Stage
# any values a function returns need to be labeled with the `stage_outputs` parameter
my_test_stage = Stage(test_function, stage_outputs=["test_func_var3", "test_func_var4"])

# we can run this stage with the run method and store the results
result = my_test_stage.run(1, 2, 3)
# result will return a dictionary containing: {"test_func_var3": 3, "test_func_var4": 5}

# running it again with different parameters
result = my_test_stage.run(2, 3, 4)
# result will return a dictionary containing: {"test_func_var3": 5, "test_func_var4": 7}

# lets write a 2nd function that can take input from our test_function
# note that the input arguments for this function should match the key names of the
# stage outputs for test_function
def test_function2(test_func_var3, test_func_var4):
    return test_func_var3 + test_func_var4

# and wrap this in a Stage
my_test_stage2 = Stage(test_function2, stage_outputs=["test_func2_var0"])

# to run this we just merely need to **results (kwarg unpacking) to pass information
# from my_test_stage to my_test_stage2
result2 = my_test_stage2.run(**results)
# result2 will return a dictionary containing: {"test_func2_var0": 12}

# or running the entire pipeline from the beginning
result2 = my_test_stage2.run(my_test_stage.run(1, 2, 3))
# result2 will return a dictionary containing: {"test_func2_var0": 8}

# We can create static values in our Stage object, so that inputs from other stages
# will be ignored

# Stage will take the same params as test_function
# and use them as static values
my_test_stage = Stage(
    test_function,
    stage_outputs=["test_func_var3", "test_func_var4"],
    test_func_var0=1,
    test_func_var1=2,
    test_func_var2=3
)

# when we run the stage, we will see that it does not change with the input
result = my_test_stage.run(2, 3, 4)
# result will return a dictionary containing: {"test_func_var3": 3, "test_func_var4": 5}
```

We can wrap the functions we write into a `Stage`, but what benefit does this provide?
The main feature of `memori` is to `memoize` the inputs to each stage and recall the outputs
if they are the same. This can enable long running functions to be skipped if the results
are going to be the same!

```
# To enable memoization feature, we need to add the hash_output parameter to the
# when constructing a Stage object. hash_output is just some directory to where the
# memoization files can be written to.
my_test_stage = Stage(test_function, stage_output=["test_func_var3", "test_func_var4"], hash_output="/test/directory")

my_test_stage.run(1, 2, 3)
# This will write 3 files: test_function.inputs, test_function.stage, test_function.outputs
# at the location: /test/directory
# These 3 files record the important states of the Stage for memoization, after it has
# been run.

```

When passing path/file strings between `Stage` objects, `memori` has special behavior: if it
determines the string to be a valid file on the disk, it will hash it with the SHA256
algoritm. For files, this gives memoization results that can reflect changes in data integrity.

`memori` also does some rudimentary static analysis to check whether and code
wrapped by a Stage has changed in a way that will affect the result. If it has 
detected this, it will rerun the stage in the same way as if the inputs provided
were different.

> **CAUTION**: One thing to note, is that `memori` uses JSON to memoize and pass information 
> between `Stage` objects. This means that the inputs/outputs of your function MUST be JSON
> serializable or you will get a serialization error.
>
> For data that is not JSON serializable, the typical workaround is to save it to a file
> and pass the file location between the `Stage` objects. This also allows you to take
> advantage of the SHA256 file hashing features of `memori`.

### `Pipeline`

What happens when you have more complex pipelines? Maybe you have a `Stage`
that needs to provide input to two different `Stage` objects.

This is where the `Pipeline` object comes in. A `Pipeline` is a collection of Stage
objects with their input/output connections defined. A `Pipeline` object represents
the conceptual DAG that was mentioned above.

```
# create some stages
stage0 = Stage(# some params go here...)
stage1 = Stage(# some params go here...)
stage2 = Stage(# some params go here...)
stage3 = Stage(# some params go here...)

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
result = p.run(# some input parameters here)
```
