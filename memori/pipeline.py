import os
from typing import Dict, List
from .stage import Stage


class Pipeline:
    """This class defines a processing pipeline linking multiple Stages.

    The definition list accepts a tuple of Stage objects with the
    following syntax:

    Examples
    --------
    >>> # the start keyword is for stages that do not have input from other stages
    >>> spec = [("start", stage0), (stage0, stage1), ((stage0, stage1), stage2)]
    >>> # last entry has multiple inputs to another stage
    >>> # create the pipeline object
    >>> pipeline = Pipeline(spec)
    >>> # run the pipeline
    >>> pipeline.run()

    Stages are run in the order that they are defined in (In the example above: stage0 -> stage1 -> stage2).

    Parameters
    ----------
    definition: List
        A list of tuples containing Stage objects that define how a pipeline is connected.

    Methods
    -------
    run:
        Runs the pipeline.
    """

    def __init__(self, definition: List):
        # save the pipeline definition
        self.definition = definition

        # verify that all inputs are stage objects
        stages = list()  # dump all pipeline definitions into single list
        for input_stages, output_stages in self.definition:
            if not isinstance(input_stages, tuple):
                input_stages = (input_stages,)
            stages.append(output_stages)
            stages.extend(input_stages)
        for stage in stages:  # check stages for invalid type
            if not (isinstance(stage, Stage) or stage == "start"):
                raise ValueError("Found invalid input %s to pipeline definition!" % stage)

        # initialize results
        self.pipeline_results = dict()

    def run(self, *args, **kwargs) -> Dict:
        """Runs the pipeline. Any stages linked to a "start" keyword accepts
        the input args/kwargs from this run method call.

        Parameters
        ----------
        *args:
            Positional arguments to pass to the first stage in the pipeline.
        **kwargs:
            Keyword arguments to pass to the first stage in the pipeline.

        Returns
        -------
        Dict
            Dictionary containing the results of the pipeline (results of all stages).
        """
        for input_stages, stage_to_run in self.definition:
            # check in input_stages is a "start" stage
            if input_stages == "start":
                # use input args/kwargs for calling stage
                stage_to_run.run(*args, **kwargs)
            else:  # find the inputs required from the input stages
                # create dictionary for input arguments
                input_args = dict()

                # make input_stages a tuple if not already one
                if not isinstance(input_stages, tuple):
                    input_stages = (input_stages,)

                # combine all results from input_stages into one dictionary
                combined_results = dict()
                for s in input_stages:
                    combined_results.update(s.results)
                combined_results.update(stage_to_run.args)

                # loop through calling stage inputs
                for arg in stage_to_run.inputs:
                    # get matching argument from combined results
                    try:
                        input_args[arg] = combined_results[arg]
                    except KeyError:  # ignore KeyErrors
                        # Let any argument exceptions be handled by python
                        pass

                # run the stage with the input_args
                try:
                    stage_to_run.run(**input_args)
                except Exception as error:
                    # give some debugging info to diagnosis why this stage
                    # failed to run
                    print("\n\ninput_args: %s" % input_args)
                    print("\n\npipeline_results: %s\n\n" % combined_results)

                    # reraise exception
                    raise error

            # update pipeline results
            self.pipeline_results.update(stage_to_run.stage_results)

        # return results
        return self.pipeline_results

    @property
    def results(self) -> Dict:
        """Dict: A dictionary of the output return values for the pipeline."""
        return self._get_abspaths(self.pipeline_results)

    def _get_abspaths(self, dictionary: Dict):
        """Convert all valid paths in dictionary to absolute path"""
        new_dict = dictionary.copy()

        # loop over keys in dictionary
        for key in new_dict:
            # get value at key
            value = new_dict[key]

            # test if value is an existing file
            if isinstance(value, str) and os.path.isfile(value):
                # convert path to absolute path
                new_dict[key] = os.path.abspath(value)
            # test if value is another dictionary, run recursive function
            elif isinstance(value, dict):
                new_dict[key] = self._get_abspaths(value)

        # return dictionary
        return new_dict


def redefine_result_key(dictionary: Dict, from_key: str, to_key: str) -> Dict:
    """Redefines a result key in the dictionary to a different key.

    Examples
    --------
    >>> dictionary = {"hello": 1, "test": 2}
    >>> new_dict = redefine_result_key(dictionary, "hello", "testing")
    >>> # new_dict is now: {"testing": 1, "test": 2}

    Parameters
    ----------
    dictionary: Dict
        Dictionary to change key of.
    from_key: str
        Key to change.
    to_key: str
        Key to replace with.

    Returns
    -------
    Dict
        New dictionary with replaced keys.
    """
    # get dictionary
    new_dict = dictionary.copy()

    # assign to_key, from_key value
    new_dict[to_key] = dictionary[from_key]

    # delete from key
    del new_dict[from_key]

    # return dictionary
    return new_dict
