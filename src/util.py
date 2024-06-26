from time import sleep
from subprocess import PIPE, Popen
from tkinter import messagebox, NORMAL, DISABLED, END, Spinbox
from ctk import CTkEntry, CTkTextbox, filedialog
from threading import Thread
from traceback import print_exc
import os
import re
from concurrent.futures import Future
from typing import IO, Iterable, Optional
from queue import Queue, Empty


CRLF = b"\r\n"
LF = b"\n"


class Tag(str):
    ERROR = "error"
    SUCCESS = "success"
    SYSTEM = "system"
    NORMAL = None


class Key(int):
    ENTER = 13
    SPACE = 32
    ESCAPE = 27


def select_directory(title: str = "Select Folder", default: Optional[str] = None) -> Optional[str]:
    selected_directory: str = filedialog.askdirectory(title=title)

    if not selected_directory:
        return default

    if not os.path.isdir(selected_directory):
        messagebox.showerror(
            "Error", "Directory is invalid.\n\nPlease select a valid directory."
        )
        return default

    if (
        selected_directory.find(" ") != -1
        or selected_directory.find("(") != -1
        or selected_directory.find(")") != -1
    ):
        messagebox.showerror(
            "Error",
            "Directory path is invalid.\n\nPlease select a directory path without spaces or parentheses.",
        )
        return default

    return selected_directory


def select_file(
    filetypes: Iterable[str] = (("All Files", "*.*"),),
    title: str = "Open",
    default: Optional[str] = None,
) -> Optional[str]:
    selected_file: str = filedialog.askopenfilename(filetypes=filetypes, title=title)

    if not selected_file:
        return default

    if not os.path.isfile(selected_file):
        messagebox.showerror(
            "Error", "File path is invalid.\n\nPlease select a valid file path."
        )
        return default

    if (
        selected_file.find(" ") != -1
        or selected_file.find("(") != -1
        or selected_file.find(")") != -1
    ):
        messagebox.showerror(
            "Error",
            "File path is invalid.\n\nPlease select a file path without spaces or parentheses.",
        )
        return default

    return selected_file


def threaded(fn) -> Future:
    """@threaded decorator from https://stackoverflow.com/a/19846691"""

    def call_with_future(fn, future, args, kwargs):
        try:
            result = fn(*args, **kwargs)
            future.set_result(result)
        except Exception as exc:
            print_exc()  # LOGGER
            future.set_exception(exc)

    def wrapper(*args, **kwargs):
        future = Future()
        Thread(target=call_with_future, args=(fn, future, args, kwargs)).start()
        return future

    return wrapper


def to_linux_path(path: str) -> str:
    path = os.path.abspath(path)
    path = path.replace(path[0], path[0].lower(), 1)
    path = re.sub(r"(\w)(:\\)", r"/mnt/\1/", path)
    path = path.replace("\\", "/")
    if " " in path:
        path = f'"{path}"'
    return path


def try_pass_except(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except Exception:
        pass


def run_bash_command(command: str, temp_path: Optional[str] = None) -> Optional[Popen]:
    file_name = "tmp.sh"

    os.makedirs(temp_path, exist_ok=True)

    if not temp_path:
        temp_file = file_name
    else:
        temp_file = os.path.join(temp_path, file_name)

    try:
        with open(temp_file, "wb") as bash_file:
            bash_file.write(
                f'#!/bin/bash\n{command}\nrm "$0"'.encode("UTF-8").replace(CRLF, LF)
            )  # scary rm command
    except Exception as e:
        messagebox.showerror(
            "Error", f"An error occurred while creating the bash file.\n\n{e}"
        )

        return None

    process = Popen(
        f"wsl -e {to_linux_path(temp_file)}",
        stdout=PIPE,
        stderr=PIPE,
        text=True,
    )

    run_after(process, try_pass_except, os.remove, temp_file)

    return process


@threaded
def run_after(process: Popen, func, *args, **kwargs):
    process.wait()
    func(*args, **kwargs)


@threaded
def enqueue_output(out: IO, queue: Queue, tag: Optional[str] = None):
    """Credit: https://stackoverflow.com/a/4896288"""
    for token in out:
        queue.put((tag, token))
    out.close()


def sanitize_filename(filename: str) -> str:
    return filename.replace("/", "-").replace(" ", "-").strip(".")


def force_insertable_value(
    new_value: float,
    widget: Spinbox | CTkEntry,
):
    validation = widget.cget("validate")
    widget.configure(validate="none")
    widget.delete(0, END)
    widget.insert(0, new_value)
    widget.configure(validate=validation)


def update_cmd_output(message: str, output_target: CTkTextbox, *tags: str):
    output_target.configure(state=NORMAL)
    is_at_end = output_target.yview()[1] > 0.95
    output_target.insert(END, message, tags)
    if is_at_end:
        output_target.see(END)
    output_target.configure(state=DISABLED)
    output_target.update_idletasks()


def display_process_output(
    process: Popen,
    output_target: CTkTextbox = None,
    refresh_timeout: int = 0,
    message_buffer: int = 1,
):
    messages = Queue()
    message_buffer = max(1, message_buffer)

    enqueue_output(process.stdout, messages, Tag.NORMAL)
    enqueue_output(process.stderr, messages, Tag.ERROR)

    pack_string = ""
    message_count = 0

    while (result := process.poll()) is None:
        try:
            tag, message = messages.get(timeout=0.1)
            pack_string += message
            if not message_count % message_buffer:
                if message_buffer > 1:
                    if output_target:
                        update_cmd_output(pack_string, output_target, Tag.NORMAL)
                    else:
                        print(pack_string, end="")
                else:
                    if output_target:
                        update_cmd_output(pack_string, output_target, tag)
                    else:
                        print(f"{tag}: {pack_string}", end="")
                pack_string = ""
            message_count += 1
        except Empty:
            pass

        sleep(refresh_timeout / 1000)

    while messages.qsize() > 0:
        tag, message = messages.get()
        pack_string += message

    if pack_string:
        if output_target:
            update_cmd_output(
                pack_string, output_target, Tag.ERROR if result else Tag.NORMAL
            )
        else:
            print(pack_string, end="")


def quote_space(string: str) -> str:
    return f'"{string}"' if " " in string else string
