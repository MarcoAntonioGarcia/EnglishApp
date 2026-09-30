#!/usr/bin/env python3
"""Fija la contraseña de un usuario.

La pide por terminal SIN mostrarla y guarda únicamente su hash scrypt. La
contraseña en claro no se escribe en disco, ni en el historial del shell, ni en
ningún log: por eso se pide aquí y no se pasa como argumento.

    python3 set_password.py marco.garcia
    python3 set_password.py ana@ejemplo.com --activar
"""
from __future__ import annotations

import argparse
import getpass
import sys

import core


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("login", help="username o correo del usuario")
    ap.add_argument("--activar", action="store_true",
                    help="además, deja la cuenta como 'active'")
    args = ap.parse_args()

    db = core.DatabaseManager()
    fila = db.find_user(args.login)
    if not fila:
        print(f"No hay ningún usuario '{args.login}'.", file=sys.stderr)
        return 1

    print(f"Usuario : {fila['username']}  (rol {fila['role']}, estado {fila['status']})")
    try:
        clave = getpass.getpass("Contraseña nueva: ")
        otra = getpass.getpass("Repítela        : ")
    except (KeyboardInterrupt, EOFError):
        print("\nCancelado.", file=sys.stderr)
        return 1

    if clave != otra:
        print("No coinciden.", file=sys.stderr)
        return 1
    problema = core.problema_con_la_clave(clave)
    if problema:
        print(problema, file=sys.stderr)
        return 1

    db.set_password(fila["id"], clave)
    if args.activar:
        db.set_user_status(fila["id"], "active")

    print("Hecho. Se han cerrado las sesiones que tuviera abiertas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
