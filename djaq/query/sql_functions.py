import functools

from djaq.functions import function_whitelist


@functools.lru_cache()
def func_in_whitelist(funcname):
    return funcname.upper() in function_whitelist


def concat(funcname, args):
    """Return args spliced by sql concat operator."""
    return " || ".join(args)


def cast(funcname, args):
    t = args[1].replace("'", "").replace("'", "")
    r = f"{args[0]}::{t}"
    return r


def index_choice0(funcname, args):
    """
    index_choice(status, "live", "not-live", "decommissioned")
    """

    index = args.pop(0)
    s = f"CASE {index} "
    for i, a in enumerate(args):
        s += f"WHEN {i} THEN {a} "
    s += "END"
    return s


djaq_functions = {
    "IIF": "CASE WHEN {} THEN {} ELSE {} END",
    "LIKE": "{} LIKE {}",
    "ILIKE": "{} ILIKE {}",
    # "CONTAINS": "{} ILIKE '%%{}%%'",
    "REGEX": "{} ~ {}",
    "CONCAT": concat,
    "TODAY": "CURRENT_DATE",
    "CAST": cast,
    "POINTX": "ST_X({})",
    "POINTY": "ST_Y({})",
    "INDEX_CHOICE0": index_choice0,
    "COUNTDISTINCT": "COUNT(DISTINCT {})",
    "SUMIF": "SUM(CASE WHEN {} THEN {} ELSE {} END)",
}

# which functions signal that we need to group by all columns that are not aggregate functions
# we have to include as well our custom functions that use aggregate functions

aggregate_functions = {
    "unknown": ["avg", "count", "max", "min", "sum"],
    "sqlite": ["avg", "count", "group_concat", "max", "min", "sum", "total"],
    "postgresql": ["avg", "count", "max", "min", "sum", "stddev", "variance", "sumif"],
}


def build_case_statement_from_choices(field_exp, choices):
    cases = ""
    for c in choices:
        cases += f"WHEN ({field_exp} = '{c[0]}') THEN '{c[1]}' "
    return f"""
        CASE
        {cases}
        END
        """
