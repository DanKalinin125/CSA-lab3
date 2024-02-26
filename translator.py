from __future__ import annotations

import sys

from isa import (
    Opcode,
    branch_instructions,
    one_parameter_instructions,
    two_parameter_instructions,
    write_code,
    zero_parameters_instructions,
)


def command_to_opcode(command):
    """Отображение операторов исходного кода в коды операций."""

    return {
        "nop": Opcode.NOP,
        "hlt": Opcode.HLT,
        "inc": Opcode.INC,
        "dec": Opcode.DEC,
        "add": Opcode.ADD,
        "sub": Opcode.SUB,
        "mov": Opcode.MOV,
        "test": Opcode.TEST,
        "jg": Opcode.JG,
        "jz": Opcode.JZ,
        "jnz": Opcode.JNZ,
        "jmp": Opcode.JMP,
    }.get(command, Opcode.NOP)


def read_asm(source_filename: str) -> list[str]:
    """Прочитать код из файла asm

    Возвращает список строк из указанного файла,
    удаляются отступы в начале и конце строки,
    удалаются пустые строки
    """

    lines = []
    with open(source_filename) as file:
        for line in file:
            line = line.strip()
            if line != "":
                lines.append(line)
    return lines


def delete_comments(lines: list[str]) -> list[str]:
    """Удалить комментарии из кода

    Распознает и удаляет из кода комментарии,
    т.е. все символы после и включая ';'
    """

    lines_without_comments = []
    for line in lines:
        comment_index = line.find(";")
        if comment_index == -1:
            lines_without_comments.append(line)
        elif comment_index != 0:
            line = line[:comment_index]
            line = line.strip()
            lines_without_comments.append(line)
    return lines_without_comments


def is_label(line: str) -> bool:
    """Проверяет является ли строка меткой

    Возвращает bool значение: true - является, false - не является
    """
    return line.endswith(":")


def is_word(line: str) -> bool:
    """Проверяет является ли строка словом (.word)

    Возвращает bool значение: true - является, false - не является
    """

    return line.startswith(".word")


def word_is_str(word: str) -> bool:
    """Проверяет является ли слово (.word) стокой

    Возвращает bool значение true - является, false - не является
    """

    return word.startswith("'") and word.endswith("'")


PROGRAM_START_POSITION_IN_MEMORY = 4  # Считается, что до этого хранится служебная информация, изменение которой


# недопустимо


def find_labels(lines: list[str]) -> dict:
    """Находит все метки в коде и их дальнейшие позиции в машинном коде

    Возвращает словарь ключ-значение: ключ - label_name, значение - label_position
    """

    labels = {}  # Хранит по ключ label_name значение label_position
    position = PROGRAM_START_POSITION_IN_MEMORY
    for line in lines:
        if is_label(line):  # Строка соответствует метке
            assert line not in labels, "Code error: label redefinition"
            labels[line[:-1]] = position

        elif is_word(line):  # Строка соответствует слову (.word)
            word = line[6::]
            if word_is_str(word):  # Данные строкового типа
                position += len(word[1:-1]) + 1  # +1, так как считаем нуль-терминатор
            else:  # Данные числового типа или сслыка на метку
                position += 1

        else:  # Строка соответствует команде
            position += 1
    return labels


def find_words(lines: list[str], labels: dict) -> list:
    """Находит все слова (.word) в коде и преобразует их в машинный код

    Возвращает машинный код со всеми найденными словами
    """

    words = []
    position = PROGRAM_START_POSITION_IN_MEMORY
    for line in lines:
        if is_word(line):  # Строка соответствует слову (.word)
            word = line[6::]
            if word_is_str(word):  # Данные строкового типа
                for symbol in word[1:-1]:
                    words.append(
                        {
                            "index": position,
                            "opcode": Opcode.NOP,
                            "arg_1": str(ord(symbol)),
                            "is_indirect_1": False,
                            "arg_2": None,
                            "is_indirect_2": None,
                        }
                    )
                    position += 1

                words.append(
                    {
                        "index": position,
                        "opcode": Opcode.NOP,
                        "arg_1": str(0),
                        "is_indirect_1": False,
                        "arg_2": None,
                        "is_indirect_2": None,
                    }
                )
                position += 1

            elif word.isdigit():  # Данные числового типа
                words.append(
                    {
                        "index": position,
                        "opcode": Opcode.NOP,
                        "arg_1": word,
                        "is_indirect_1": False,
                        "arg_2": None,
                        "is_indirect_2": None,
                    }
                )
                position += 1

            elif word in labels:  # Данные - ссылка на метку
                words.append(
                    {
                        "index": position,
                        "opcode": Opcode.NOP,
                        "arg_1": str(labels[word]),
                        "is_indirect_1": False,
                        "arg_2": None,
                        "is_indirect_2": None,
                    }
                )
                position += 1

            else:  # Не предвиденный тип данных для слова (.word)
                raise AssertionError("Code error: incorrect word" + word)

        elif not (is_label(line)):  # Строка соответствует команде
            position += 1

    return words


REGISTERS = ["r0", "r1", "r2", "r3"]


def parse_address(address: str, opcode: Opcode, labels: dict) -> tuple[str, bool]:
    """Парсит адрес из аргумента команды

    Определяет обладает ли адрес косвенной адресацией,
    проверяет адрес на обязательное наличие среди чисел, меток и регистров,
    проверяет адрес на обязаельность reg-to-reg оперций для рассматриваемой команды.

    Возвращает "очищенный" адрес и признак косвенной адресации
    """

    if address.startswith("(") and address.endswith(")"):
        is_indirect = True
        address = address[1:-1]
    else:
        is_indirect = False

    assert address.isdigit() or address in labels or address in REGISTERS, "Code error: missing address " + address

    if address in labels:
        if opcode != Opcode.MOV and opcode not in branch_instructions:
            raise AssertionError("Code error: command " + str(opcode) + " only register-to-register")
        address = str(labels[address])

    return address, is_indirect


def parse_command_to_code(line: str, position: int, labels: dict) -> dict:
    """Переводит строку, соответствующую команде в машинный код

    Проверяет команду на наличие в заданном языке программирования,
    Проверяет команду на корректное число её аргументов.

    Возвращает машинный код команды
    """

    command = line.split(" ")[0]
    opcode = command_to_opcode(command)
    assert opcode != Opcode.NOP, "Code error: there is no such command " + command

    arg_1 = None
    is_indirect_1 = None
    arg_2 = None
    is_indirect_2 = None

    if command in zero_parameters_instructions:
        assert len(line.split(" ")) == 1, "Code error: the command " + command + " must have 0 args"

    elif command in branch_instructions or command in one_parameter_instructions:
        assert len(line[len(command) + 1 : :].split(", ")) == 1, (
            "Code error: the command " + command + " must have 1 args"
        )
        arg_1, is_indirect_1 = parse_address(line[len(command) + 1 : :].split(", ")[0], opcode, labels)

    elif command in two_parameter_instructions:
        assert len(line[len(command) + 1 : :].split(", ")) == 2, (
            "Code error: the command " + command + " must have 2 args"
        )
        args = line[len(command) + 1 : :].split(", ")
        arg_1, is_indirect_1 = parse_address(args[0], opcode, labels)
        arg_2, is_indirect_2 = parse_address(args[1], opcode, labels)

    return {
        "index": position,
        "opcode": opcode,
        "arg_1": arg_1,
        "is_indirect_1": is_indirect_1,
        "arg_2": arg_2,
        "is_indirect_2": is_indirect_2,
    }


def find_code(lines: list[str], labels: dict) -> list:
    """Находит все команды в коде и преобразует их в машинный код

    Возвращает машинный код найденных команд
    """

    code = []
    position = PROGRAM_START_POSITION_IN_MEMORY
    for line in lines:
        if not (is_label(line) or is_word(line)):  # Строка соответствует команде
            code.append(parse_command_to_code(line, position, labels))
            position += 1

        elif is_word(line):  # Строка соответствует данным
            word = line[6::]
            if word_is_str(word):  # Данные строкового типа
                position += len(word[1:-1]) + 1  # +1, так как считаем нуль-терминатор
            else:  # Данные числового типа или сслыка на метку
                position += 1
    return code


def find_start(labels: dict) -> list:
    """Определяет машинный код команды jmp _start

    Находит метку _start среди меток и возвращает машинный код начала программы
    """

    assert "_start" in labels, "Code error: Label _start not found"
    return [
        {
            "index": 0,
            "opcode": Opcode.JMP,
            "arg_1": str(labels["_start"]),
            "is_indirect_1": False,
            "arg_2": None,
            "is_indirect_2": None,
        }
    ]


def translate(lines: list[str]):
    """Переводит исходную программу в машинный код"""

    lines = delete_comments(lines)

    labels = find_labels(lines)
    start = find_start(labels)
    words = find_words(lines, labels)
    code = find_code(lines, labels)

    return start + words + code


def main(source_filename: str, target_filename: str):
    lines = read_asm(source_filename)
    code = translate(lines)
    write_code(target_filename, code)

    print("Translate to " + target_filename)


if __name__ == "__main__":
    assert len(sys.argv) == 3, "Wrong arguments: translator.py <input_file> <target_file>"
    _, source_filename, target_filename = sys.argv
    main(source_filename, target_filename)