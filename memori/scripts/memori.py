import os
import signal
import argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from memori.helpers import script_to_python_func
from memori.logging import setup_logging
from memori import Stage


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "-c", "--dependents", nargs="+", help="Other scripts/commands that the current command depends on."
    )
    parser.add_argument("-o", "--outputs", nargs="+", help="Expected file outputs for the current script.")
    parser.add_argument("-d", "--hash_output", help="Location to write hash files to (Default: None)")
    parser.add_argument("-n", "--name", help="Alternative name for hash files (Default: name of command)")
    parser.add_argument(
        "-p",
        "--parallel",
        type=int,
        help="Number of parallel processes to use. When -p/--parallel is specified use the `--argX` flag to "
        "specify arguments to run for each parallel process and --arg_outputX to specify expected outputs for "
        "each parallel process (where X is a number, starting from 0)",
    )
    parser.add_argument("-k", "--kill", action="store_true", help="Kill parent script/process on fail.")
    parser.add_argument("--log_file", help="Location to write log file to (--verbose must be on) (Default: None)")
    parser.add_argument("--verbose", help="Prints memori verbose info", action="store_true")

    # parse for dynamic args
    dynamic_args = parser.parse_known_args()[1]

    # create new parser for dynamic args
    parser = argparse.ArgumentParser(
        parents=[parser],
        description="""memori command-line script memoization.
        This program memoizes inputs and outputs of a given script/command and detects changes
        to it through sha256 checksums. If the script/command's hash changes or if any inputs/outputs
        to the script change, memori will rerun the script/command, if not it will skip it's execution.
        Since memori only detects command changes through checksums, it is important to use the
        -c/--dependents flag and manually specify any dependent scripts/commands that a script calls. If not,
        execution will be skipped even if changes were made to those scripts/commands. The -o/--outputs flag
        denote expected outputs of the script/command and is used to ensure file integrity of it's outputs
        (e.g. if a file was moved/renamed/modified).
        You can direct the output of the generated cached files with the -d/--hash_output flag.
        """,
        epilog="Andrew Van <vanandrew@wustl.edu> 11/29/2022",
    )
    parser.add_argument("command", nargs="+", help="Command to run and any subsequent arguments")

    # check args for dynamic args beginning with --arg
    n = 0
    for arg in dynamic_args:
        if arg.startswith("--arg") and "output" not in arg:
            parser.add_argument(f"--arg{n}", nargs="+", help=f"Parallel argument.")
            n += 1
    num_dynamic_args = n - 1

    # check args for dynamic args beginning with --arg_output
    for arg in dynamic_args:
        if arg.startswith("--arg_output"):
            parser.add_argument(arg, nargs="+", help=f"Expected output for argument.")

    args = parser.parse_args()

    # turn on logging if verbose on
    if args.verbose:
        setup_logging(args.log_file)

    # split command and arguments
    command = args.command[0]
    arguments = args.command[1:]

    # combine command and dependent scripts
    scripts = [
        command,
    ]
    if args.dependents:
        scripts.extend(args.dependents)

    # use parallel processes if specified
    if args.parallel:
        # get dynamic args
        if num_dynamic_args == -1:
            raise ValueError("No dynamic args specified.")
        dynamic_args = {
            key: value for key, value in vars(args).items() if key.startswith("arg") and "output" not in key
        }
        expected_outputs = {key: value for key, value in vars(args).items() if key.startswith("arg_output")}
        with ProcessPoolExecutor(max_workers=args.parallel) as executor:
            # for each dynamic arg, run stage
            futures = {i: None for i, _ in enumerate(dynamic_args)}
            for idx, arguments in dynamic_args.items():
                arg_num = int(idx.split("g")[1])
                hash_output = Path(args.hash_output) / f"parallel{arg_num}" if args.hash_output else None
                stage_outputs = None
                arg_outputs = None
                if f"arg_output{arg_num}" in expected_outputs:  # if expected outputs specified
                    arg_outputs = expected_outputs[f"arg_output{arg_num}"]
                    stage_outputs = [
                        "output",
                    ]
                    stage_outputs.extend([f"output{i}" for i in range(len(arg_outputs))])
                # submit job and store future
                futures[arg_num] = executor.submit(
                    Stage(
                        script_to_python_func(scripts, len(arguments), arg_outputs),
                        stage_name=args.name,
                        stage_outputs=stage_outputs,
                        hash_output=hash_output,
                    ).run,
                    *arguments,
                )

            # get results
            results = [future.result() for future in as_completed([v for v in futures.values()])]

            # check if any results failed
            out_dict = {"output": 0}
            if any([i["output"] == 1 for i in results]):
                out_dict["output"] = 1

    else:  # run single process
        # get function to run
        func = script_to_python_func(scripts, len(arguments), args.outputs)

        # set stage outputs if provided
        stage_outputs = None
        if args.outputs:
            stage_outputs = [
                "output",
            ]
            stage_outputs.extend([f"output{i}" for i in range(len(args.outputs))])

        # run function in stage
        out_dict = Stage(func, stage_name=args.name, stage_outputs=stage_outputs, hash_output=args.hash_output).run(
            *arguments
        )

    # kill parent process if specified
    if args.kill:
        os.kill(os.getppid(), signal.SIGKILL)

    # return output
    return out_dict["output"]
