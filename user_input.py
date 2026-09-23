def ask_choice(question, options, default=None):
    """Display a numbered list of options and return the selected one.

    If `default` is given, the user can just press Enter to select it.
    """
    print(question)
    for i, option in enumerate(options, start=1):
        marker = " (default)" if option == default else ""
        print(f"  {i}. {option}{marker}")

    while True:
        answer = input("Your choice: ").strip()
        if answer == "" and default is not None:
            return default
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return options[int(answer) - 1]
        print(f"Please enter a number between 1 and {len(options)}.")