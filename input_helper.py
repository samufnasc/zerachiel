import msvcrt
import sys

def get_input():
    """
    Lê uma linha de entrada do terminal de forma não-bloqueante.
    Retorna a string digitada ou None se nada foi digitado.
    """
    if msvcrt.kbhit():
        # Se houver uma tecla, lemos a linha inteira
        # Como o msvcrt.getch() lê byte a byte, vamos capturar o buffer do console
        import os
        import subprocess

        # No Windows, uma forma de ler o buffer sem bloquear é usar o comando 'choice'
        # ou ler via msvcrt até o ENTER.
        chars = []
        while msvcrt.kbhit():
            char = msvcrt.getch()
            if char in (b'\r', b'\n'): # ENTER
                break
            if char == b'\x08': # BACKSPACE
                if chars:
                    chars.pop()
            else:
                try:
                    decoded = char.decode('utf-8')
                    chars.append(decoded)
                except:
                    pass

        result = "".join(chars)
        return result if result else None
    return None
