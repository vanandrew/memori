import argparse
from memori.helpers import script_to_python_func
from memori.logging import setup_logging
from memori import Stage


def main():
    parser = argparse.ArgumentParser(
        description="""memori script memoization.
        This program memoizes inputs and outputs of a given command and detects changes
        to it through sha256 checksums. If the command's hash changes or if any inputs/outputs
        to the script change, memori will rerun the script, if not it will skip command execution.
        Since memori only detects command changes through checksums, it is important to use the
        -s/--script flag and manually specify any dependent scripts/commands that a script calls. If not,
        execution will be skipped even if changes were made to those scripts/commands. The -o/--outputs flag
        denote expected outputs of the script/command and is used to ensure file integrity of it's outputs
        (e.g. if a file was moved/renamed/modified).
        """,
        epilog="Andrew Van <vanandrew@wustl.edu> 11/29/2022",
    )
    parser.add_argument("command", nargs="+", help="Command to run and any subsequent arguments")
    parser.add_argument(
        "-s", "--scripts", nargs="+", help="Other scripts/commands that the current command depends on."
    )
    parser.add_argument("-o", "--outputs", nargs="+", help="Expected file outputs for the current script.")
    parser.add_argument("-d", "--hash_output", help="Location to write hash files to (Default: None)")
    parser.add_argument("-n", "--name", help="Alternative name for hash files (Default: name of command)")
    parser.add_argument("--verbose", help="Prints memori verbose info", action="store_true")
    args = parser.parse_args()

    # turn on logging if verbose on
    if args.verbose:
        setup_logging()

    # split command and arguments
    command = args.command[0]
    arguments = args.command[1:]

    # combine command and dependent scripts
    scripts = [
        command,
    ]
    if args.scripts:
        scripts.extend(args.scripts)

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

    # return output
    return out_dict["output"]
