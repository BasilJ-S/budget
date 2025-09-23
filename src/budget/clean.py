import pandas as pd
from dataclasses import dataclass, asdict
import yaml
import datetime as dt


@dataclass
class Rule:
    string_to_match: str
    keep: bool = True

@dataclass
class Ruleset:
    rules: list[Rule]

def read_data():
    debit = pd.read_csv('src/budget/data/checking.csv')
    credit = pd.read_csv('src/budget/data/visa.csv')
    # drop last column
    credit = credit.iloc[:, :-1]
    debit['type'] = 'debit'
    debit.columns = ['date', 'description', 'out','in', 'type']
    credit['type'] = 'credit'
    credit.columns = ['date', 'description', 'out','in', 'type']
    df = pd.concat([debit, credit])
    df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%d')

    return df

def apply_rules(df, rules):
    
    # Apply row removals
    for rule in rules.rules:
        if not rule.keep:
            df = df[~df['description'].str.contains(rule.string_to_match)]
    return df



if __name__ == "__main__":
    # Load and clean data
    df = read_data()

    # Read existing rules (if any)
    try:
        with open('src/budget/rulesets/rules.yaml', 'r') as f:
            rules_dict = yaml.safe_load(f)
            ruleset = Ruleset(rules=[Rule(**rule) for rule in rules_dict['rules']])
    except FileNotFoundError:
        ruleset = Ruleset(rules=[])
    print(ruleset)
    # Apply rules
    df = apply_rules(df, ruleset)

    # Save filtered transactions
    df.to_csv('src/budget/data/transactions.csv', index=False)

    # Write rules to YAML
    with open('src/budget/rulesets/rules.yaml', 'w') as f:
        yaml.dump(asdict(ruleset), f)

    # Write a timestamped copy of the ruleset
    with open(f'src/budget/rulesets/rules{dt.datetime.now().strftime("%Y%m%d_%H%M%S")}.yaml', 'w') as f:
        yaml.dump(asdict(ruleset), f)
