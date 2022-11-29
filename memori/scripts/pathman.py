import argparse
from memori.pathman import PathManager as PathMan


command_spec = {
    "get_prefix": 0,
    "get_path_and_prefix": 0,
    "append_suffix": 1,
    "replace_suffix": 1,
    "delete_suffix": 0,
    "repath": 1,
}


def main():
    help_string = ""
    for c in command_spec:
        help_string += c
        help_string += ":\n    "
        help_string += PathMan.__dict__[c].__doc__
        help_string += "\n"

    description = (
        "When using the below commands, parameters are passed by position.\n"
        "For example, if you want to use the `append_suffix` command, you\n"
        "would pass the filename and suffix as follows:\n\n"
        "    pathman ${file} append_suffix ${suffix}\n\n"
        "Commands can be chained togeter:\n\n"
        "    pathman ${file} get_prefix append_suffix ${suffix}\n\n"
    )

    parser = argparse.ArgumentParser(
        description=f"Path Manager.\n\n{description}\n\nCommands:\n\n{help_string}",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="Andrew Van <vanandrew@wustl.edu> 11/29/2022",
    )
    parser.add_argument("path", help="Path to manage.")
    parser.add_argument("command", nargs="+", help="Path manipulation command.")
    args = parser.parse_args()

    # make a path manager
    pm = PathMan(args.path)

    # loop through commands and run
    skip_command = 0
    for i, command in enumerate(args.command):
        if skip_command != 0:
            skip_command -= 1
            continue
        if command not in command_spec:
            raise ValueError(f"Command {command} not recognized.")
        num_args = command_spec[command]
        if num_args == 0:
            pm = getattr(pm, command)()
        elif num_args == 1:
            pm = getattr(pm, command)(args.command[i + 1])
            skip_command = 1

    # print path
    print(pm.path)

    return 0
