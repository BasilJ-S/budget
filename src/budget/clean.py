import pandas as pd
from dataclasses import dataclass, asdict
import yaml
import datetime as dt
import numpy as np

RULESET_PATH = 'src/budget/rulesets/'
DATA_PATH = 'src/budget/data/'


@dataclass
class Rule:
    string_to_match: str
    keep: bool = True
    category: str = None

@dataclass
class Ruleset:
    rules: list[Rule]

def read_data():
    debit = pd.read_csv(f'{DATA_PATH}checking.csv')
    credit = pd.read_csv(f'{DATA_PATH}visa.csv')
    # drop last column
    credit = credit.iloc[:, :-1]
    debit['type'] = 'debit'
    debit.columns = ['date', 'description', 'out','in', 'type']
    credit['type'] = 'credit'
    credit.columns = ['date', 'description', 'out','in', 'type']
    df = pd.concat([debit, credit])
    df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%d')

    return df

def apply_rules(df, ruleset):

    df['category'] = ""
    
    # Apply row removals
    for rule in ruleset.rules:
        if not rule.keep:
            df = df[~df['description'].str.contains(rule.string_to_match, regex = False)]
        if rule.category:
            # Extend categories string to the assigned category

            matches = df['description'].str.contains(rule.string_to_match, regex = False)
            if matches.sum() > 0:
                print(matches.sum(), "matches for", rule.string_to_match, " -> ", rule.category)
                df.loc[matches, 'category'] = rule.category + ', ' + df.loc[matches, 'category']
            

    df['category'] = df['category'].str.strip(', ')
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


def categorize(df, ruleset):

    df = apply_rules(df, ruleset)

    nulls = df['category'].isnull() + (df['category'] == '')

    while nulls.sum() > 0:
        print(nulls.sum(), "uncategorized transactions remaining")

        # Gather latest uncategorized transaction
        first_null = df[nulls].iloc[0]
        description = first_null['description']
        date = first_null['date']
        amount = first_null['out'] if not pd.isna(first_null['out']) else -first_null['in'] # Positive for expense, negative for income

        # Show available categories
        shorthands = build_shorthand_category_mapping(ruleset)
        print("AVAILABLE CATEGORIES:")
        for x in range(0, len(shorthands.keys()),3):
            print("\t|\t".join([f"{k:<4}: {shorthands[k]:<15}" for k in list(shorthands.keys())[x:x+3]]))

        print(f"Uncategorized transaction\nDATE: {date}, DESC: {description}, AMOUNT: {amount}")

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
        if make_rule.lower() == 'y' or make_rule.lower() == 'yes':
            description = input("Enter string to match: ")
            print(f'Creating rule: If description contains "{description}", categorize as "{cat}"')

        # Add rule and re-apply ruleset
        ruleset.rules.append(Rule(string_to_match=description, keep=True, category=cat))
        df = apply_rules(df, ruleset)

        # Check for multiple categories in any transaction i.e. overlapping rules
        multiple_categories = any([',' in c for c in df['category'].unique()])
        if multiple_categories:
            print("ERROR: Some transactions have multiple categories assigned. This may lead to unexpected behavior.")
            break

        # Re count uncategorized transactions
        nulls = df['category'].isnull() + (df['category'] == '')

        # Autosave ruleset
        with open(f'{RULESET_PATH}rules_autosave.yaml', 'w') as f:
            yaml.dump(asdict(ruleset), f)

    
    return df, ruleset

def save_ruleset_with_backup(ruleset):
    with open(f'{RULESET_PATH}rules.yaml', 'w') as f:
        yaml.dump(asdict(ruleset), f)

    with open(f'{RULESET_PATH}rules_{dt.datetime.now().strftime("%Y%m%d_%H%M%S")}.yaml', 'w') as f:
        yaml.dump(asdict(ruleset), f)


    



if __name__ == "__main__":
    # Load and clean data
    df = read_data()

    # Read existing rules (if any)
    try:
        with open(f'{RULESET_PATH}rules.yaml', 'r') as f:
            rules_dict = yaml.safe_load(f)
            ruleset = Ruleset(rules=[Rule(**rule) for rule in rules_dict['rules']])
    except FileNotFoundError:
        ruleset = Ruleset(rules=[])
    print(build_shorthand_category_mapping(ruleset))
    # Apply rules
    df = df.sort_values(by='date', ascending=False)

    df, ruleset = categorize(df, ruleset)

    # Save filtered transactions
    df.to_csv(f'{DATA_PATH}transactions.csv', index=False)

    save_ruleset_with_backup(ruleset)
    print(f"Saved cleaned categorized transactions to {DATA_PATH}transactions.csv")
