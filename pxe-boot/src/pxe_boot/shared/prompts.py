from typing import Literal


def select_mode() -> Literal["netboot", "iso"]:
    print("Select PXE boot mode:")
    print("  1) netboot.xyz (downloads installer over internet)")
    print("  2) Direct ISO (boots a local .iso you provide)")
    while True:
        choice = input("Choice [1/2]: ").strip()
        if choice == "1":
            return "netboot"
        if choice == "2":
            return "iso"
        print("Please type 1 or 2.")
