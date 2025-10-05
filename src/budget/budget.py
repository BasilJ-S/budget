import datetime as dt
from dataclasses import asdict, dataclass, field

import yaml
from clean import RULESET_PATH, Ruleset, build_shorthand_and_list, load_ruleset

BUDGET_PATH = "src/budget/budgets/"


@dataclass
class Budget:
    name: str = "Default"
    start_date: dt.date = dt.date.today()
    end_date: dt.date = dt.date.today() + dt.timedelta(days=30)
    last_edited: dt.datetime = dt.datetime.now()
    total_budgeted: float = 0
    items: list["BudgetItem"] = field(default_factory=list)


@dataclass
class BudgetItem:
    categories: str
    budgeted_amount: float


def write_budget(budget: Budget, filename: str = None):
    if filename is None:
        filename = budget.name
    with open(f"{BUDGET_PATH}{filename}.yaml", "w") as f:
        yaml.dump(asdict(budget), f)


def save_budget(budget: Budget):
    write_budget(budget)
    write_budget(
        budget,
        filename=f'backup_{budget.name}_{dt.datetime.now().strftime("%Y%m%d_%H%M%S")}',
    )


def read_budget(budget_name: str):
    with open(f"{BUDGET_PATH}{budget_name}.yaml", "r") as f:
        budget = Budget(**yaml.safe_load(f))
        budget_items = []
        for item in budget.items:
            budget_items.append(BudgetItem(**item))
        budget.items = budget_items

        return budget


def list_budgets() -> None:
    import os

    files = os.listdir(BUDGET_PATH)
    budgets = [
        f[:-5] for f in files if f.endswith(".yaml") and not f.startswith("backup")
    ]
    return budgets


def get_budget_item(ruleset: Ruleset) -> BudgetItem:
    shorthands = build_shorthand_and_list(ruleset)
    categories = input("Enter category or categories (comma separated shorthands.: ")
    categories = [shorthands.get(cat.strip().lower()) for cat in categories.split(",")]

    amount = float(input("Enter budgeted amount: "))
    item = BudgetItem(categories=categories, budgeted_amount=amount)
    return item


def build_budget(ruleset: Ruleset) -> Budget:
    budget = edit_budget_metadata(Budget())

    return edit_budget(budget, ruleset)


def edit_budget_metadata(budget: Budget) -> Budget:
    budget.name = (
        input(f"Enter new budget name (current: {budget.name}): ") or budget.name
    )
    start_date_str = input(
        f"Enter new start date (YYYY-MM-DD) (current: {budget.start_date}): "
    )
    if start_date_str:
        budget.start_date = dt.datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_date_str = input(
        f"Enter new end date (YYYY-MM-DD) (current: {budget.end_date}): "
    )
    if end_date_str:
        budget.end_date = dt.datetime.strptime(end_date_str, "%Y-%m-%d").date()
    total_budget_str = input(
        f"Enter new total budgeted amount (current: {budget.total_budgeted}): "
    )
    if total_budget_str:
        budget.total_budgeted = float(total_budget_str)
    return budget


def print_budget_items(budget: Budget):
    if len(budget.items) == 0:
        print("No items in budget.")
        return

    print("Current items:")
    budget_left = budget.total_budgeted - sum(
        item.budgeted_amount for item in budget.items
    )
    print(
        f"Total budget: {budget.total_budgeted}, Total budgeted: {sum(item.budgeted_amount for item in budget.items)}, Budget left: {budget_left}"
    )
    for idx, item in enumerate(budget.items):
        print(
            f"{idx + 1}. Categories: {item.categories}, Amount: {item.budgeted_amount}"
        )


def edit_budget(budget: Budget, ruleset: Ruleset) -> Budget:
    print(f"Editing budget: {budget.name}")
    print_budget_items(budget)

    while True:
        action = (
            input(
                "Would you like to add, edit, or remove an item? Or modify budget metadata? (a/e/r/m/done): "
            )
            .strip()
            .lower()
        )
        if action == "a":
            new_item = get_budget_item(ruleset)
            budget.items.append(new_item)
        elif action == "e":
            item_idx = int(input("Enter the item number to edit: ")) - 1
            if 0 <= item_idx < len(budget.items):
                print(f"Editing item {item_idx + 1}")
                budget.items[item_idx] = get_budget_item(ruleset)
            else:
                print("Invalid item number.")
        elif action == "r":
            item_idx = int(input("Enter the item number to remove: ")) - 1
            if 0 <= item_idx < len(budget.items):
                del budget.items[item_idx]
                print("Item removed.")
            else:
                print("Invalid item number.")
        elif action == "m":
            budget = edit_budget_metadata(budget)

        elif action == "done":
            break
        else:
            print("Invalid action. Please enter 'a', 'e', 'r', or 'done'.")
        budget.last_edited = dt.datetime.now()
        print_budget_items(budget)
        write_budget(budget, filename=f"autosave_{budget.name}")

    return budget


if __name__ == "__main__":

    ruleset = load_ruleset()

    new_or_edit = (
        input(
            "Would you like to create a new budget or edit an existing one? (new/edit): "
        )
        .strip()
        .lower()
    )
    if new_or_edit == "edit":
        budgets = list_budgets()
        print("Available budgets:")
        for idx, bname in enumerate(budgets):
            print(f"{idx + 1}. {bname}")
        choice = int(input("Enter the number of the budget to edit: ")) - 1
        if 0 <= choice < len(budgets):
            budget = read_budget(budgets[choice])
            print(budget)
            budget = edit_budget(budget, ruleset)
        else:
            print("Invalid choice.")
    else:
        budget = build_budget(ruleset)
    save_budget(budget)
