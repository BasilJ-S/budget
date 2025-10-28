import datetime as dt
import logging
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
import yaml

RULESET_PATH = "src/budget/rulesets/"
DATA_PATH = "src/budget/data/"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(filename)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class Rule:
    string_to_match: str
    keep: bool = True
    category: str = None


@dataclass
class Ruleset:
    rules: list[Rule]


def read_data():
    debit = pd.read_csv(f"{DATA_PATH}checking.csv")
    credit = pd.read_csv(f"{DATA_PATH}visa.csv")
    savings = pd.read_csv(f"{DATA_PATH}savings.csv")
    # drop last column
    credit = credit.iloc[:, :-1]
    debit["type"] = "debit"
    debit.columns = ["date", "description", "out", "in", "type"]
    credit["type"] = "credit"
    credit.columns = ["date", "description", "out", "in", "type"]
    savings["type"] = "savings"
    savings.columns = ["date", "description", "out", "in", "type"]
    df = pd.concat([debit, credit, savings])
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d")

    return df


def apply_rules(df, ruleset):

    df["category"] = ""

    # Apply row removals
    for rule in ruleset.rules:
        if not rule.keep:
            df = df[~df["description"].str.contains(rule.string_to_match, regex=False)]
        if rule.category:
            # Extend categories string to the assigned category

            matches = df["description"].str.contains(rule.string_to_match, regex=False)
            if matches.sum() > 0:
                logger.info(
                    f"{matches.sum()} matches for {rule.string_to_match} -> {rule.category}"
                )

                df.loc[matches, "category"] = (
                    rule.category + ", " + df.loc[matches, "category"]
                )

    df["category"] = df["category"].str.strip(", ")
    return df


def build_shorthand_category_mapping(ruleset):
    categories = set()
    for rule in ruleset.rules:
        if rule.category:
            categories.add(rule.category)

    categories = sorted(list(categories))

    shorthands = {}
    for cat in categories:
        length = 1
        while True:
            shorthand = cat[:length].lower()
            if shorthand in shorthands:
                length += 1
            else:
                shorthands[shorthand] = cat
                break
            if length > len(cat):
                raise ValueError(f"Cannot create unique shorthand for category {cat}")

    return shorthands


def list_categories(shorthands) -> None:
    logger.info("AVAILABLE CATEGORIES:")
    for x in range(0, len(shorthands.keys()), 3):
        logger.info(
            "\t|\t".join(
                [
                    f"{k:<4}: {shorthands[k]:<15}"
                    for k in list(shorthands.keys())[x : x + 3]
                ]
            )
        )


def build_shorthand_and_list(ruleset):
    shorthands = build_shorthand_category_mapping(ruleset)
    list_categories(shorthands)
    return shorthands


def categorize(df, ruleset):

    df = apply_rules(df, ruleset)

    nulls = df["category"].isnull() + (df["category"] == "")

    while nulls.sum() > 0:
        logger.info(f"{nulls.sum()} uncategorized transactions remaining")

        # Gather latest uncategorized transaction
        first_null = df[nulls].iloc[0]
        description = first_null["description"]
        date = first_null["date"]
        amount = (
            first_null["out"] if not pd.isna(first_null["out"]) else -first_null["in"]
        )  # Positive for expense, negative for income

        # Show available categories
        shorthands = build_shorthand_and_list(ruleset)

        logger.info(
            f"Uncategorized transaction\nDATE: {date}, DESC: {description}, AMOUNT: {amount}"
        )

        # Collect input
        user_cat = input("Enter shorthand, new category or EXIT to end session: ")
        if user_cat.upper() == "EXIT":
            break
        if user_cat.lower() in shorthands:
            cat = shorthands[user_cat.lower()]
        else:
            cat = user_cat

        # Generate general rule if wanted
        make_rule = input("Make a general rule? (default no) (y/n): ")
        if make_rule.lower() == "y" or make_rule.lower() == "yes":
            description = input("Enter string to match: ")
            logger.info(
                f'Creating rule: If description contains "{description}", categorize as "{cat}"'
            )

        # Add rule and re-apply ruleset
        ruleset.rules.append(Rule(string_to_match=description, keep=True, category=cat))
        df = apply_rules(df, ruleset)

        # Check for multiple categories in any transaction i.e. overlapping rules
        multiple_categories = any(["," in c for c in df["category"].unique()])
        if multiple_categories:
            logger.error(
                "Some transactions have multiple categories assigned. This may lead to unexpected behavior."
            )
            break

        # Re count uncategorized transactions
        nulls = df["category"].isnull() + (df["category"] == "")

        # Autosave ruleset
        with open(f"{RULESET_PATH}rules_autosave.yaml", "w") as f:
            yaml.dump(asdict(ruleset), f)

    return df, ruleset


def save_ruleset_with_backup(ruleset):
    with open(f"{RULESET_PATH}rules.yaml", "w") as f:
        yaml.dump(asdict(ruleset), f)

    with open(
        f'{RULESET_PATH}rules_{dt.datetime.now().strftime("%Y%m%d_%H%M%S")}.yaml', "w"
    ) as f:
        yaml.dump(asdict(ruleset), f)


def load_ruleset():
    try:
        with open(f"{RULESET_PATH}rules.yaml", "r") as f:
            rules_dict = yaml.safe_load(f)
            ruleset = Ruleset(rules=[Rule(**rule) for rule in rules_dict["rules"]])
    except FileNotFoundError:
        ruleset = Ruleset(rules=[])
    return ruleset


if __name__ == "__main__":
    # Load and clean data
    df = read_data()

    # Read existing rules (if any)
    ruleset = load_ruleset()
    logger.info(build_shorthand_category_mapping(ruleset))
    # Apply rules
    df = df.sort_values(by="date", ascending=False)

    df, ruleset = categorize(df, ruleset)

    # Save filtered transactions
    df.to_csv(f"{DATA_PATH}transactions.csv", index=False)

    save_ruleset_with_backup(ruleset)
    logger.info(
        f"Saved cleaned categorized transactions to {DATA_PATH}transactions.csv"
    )
