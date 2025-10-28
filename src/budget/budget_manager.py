import datetime as dt
import logging
from dataclasses import asdict, dataclass, field

import yaml
from dash.development.build_process import logger
from numpy import isin

from budget.clean import RULESET_PATH, Ruleset, build_shorthand_and_list, load_ruleset

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(filename)s - %(message)s",
)
logger = logging.getLogger(__name__)

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
    categories: list[str]
    budgeted_amount: float


def write_budget(budget: Budget, filename: str | None = None):
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
        _data = yaml.safe_load(f)
        budget = Budget(**_data)
        budget.items = [BudgetItem(**item) for item in _data.get("items", [])]
        return budget


def list_budgets() -> list[str]:
    import os

    files = os.listdir(BUDGET_PATH)
    budgets = [
        f[:-5] for f in files if f.endswith(".yaml") and not f.startswith("backup")
    ]
    return budgets


def get_budget_item(ruleset: Ruleset) -> BudgetItem:
    shorthands = build_shorthand_and_list(ruleset)
    categories = input("Enter category or categories (comma separated shorthands): ")
    resolved_categories = [
        str(shorthands.get(cat.strip().lower(), "")) for cat in categories.split(",")
    ]
    if "" in resolved_categories:
        raise ValueError(f"Invalid category shorthand, {categories}.")

    amount = float(input("Enter budgeted amount: "))
    item = BudgetItem(categories=resolved_categories, budgeted_amount=amount)
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
        logger.info("No items in budget.")
        return

    logger.info("Current items:")
    budget_left = budget.total_budgeted - sum(
        item.budgeted_amount for item in budget.items
    )
    logger.info(
        f"Total budget: {budget.total_budgeted}, Total budgeted: {sum(item.budgeted_amount for item in budget.items)}, Budget left: {budget_left}"
    )
    for idx, item in enumerate(budget.items):
        logger.info(
            f"{idx + 1}. Categories: {item.categories}, Amount: {item.budgeted_amount}"
        )


def edit_budget(budget: Budget, ruleset: Ruleset) -> Budget:
    logger.info(f"Editing budget: {budget.name}")
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
                logger.info(f"Editing item {item_idx + 1}")
                budget.items[item_idx] = get_budget_item(ruleset)
            else:
                logger.info("Invalid item number.")
        elif action == "r":
            item_idx = int(input("Enter the item number to remove: ")) - 1
            if 0 <= item_idx < len(budget.items):
                del budget.items[item_idx]
                logger.info("Item removed.")
            else:
                logger.info("Invalid item number.")
        elif action == "m":
            budget = edit_budget_metadata(budget)

        elif action == "done":
            break
        else:
            logger.info("Invalid action. Please enter 'a', 'e', 'r', or 'done'.")
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
        logger.info("Available budgets:")
        for idx, bname in enumerate(budgets):
            logger.info(f"{idx + 1}. {bname}")
        choice = int(input("Enter the number of the budget to edit: ")) - 1
        if 0 <= choice < len(budgets):
            budget = read_budget(budgets[choice])
            logger.info(f"Editing budget: {budget.name}")
            budget = edit_budget(budget, ruleset)
        else:
            logger.info("Invalid choice.")
            exit(1)
    else:
        budget = build_budget(ruleset)
    save_budget(budget)
