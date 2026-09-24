import ast
import math
import operator
import statistics

class SafeCalculator:
    BIN = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod, ast.Pow: operator.pow
    }
    UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
    FUNCS = {
        "sqrt": math.sqrt, "abs": abs, "round": round, "floor": math.floor,
        "ceil": math.ceil, "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "log": math.log, "log10": math.log10, "exp": math.exp,
        "factorial": math.factorial, "degrees": math.degrees, "radians": math.radians,
        "mean": statistics.mean, "median": statistics.median, "stdev": statistics.stdev
    }
    CONST = {"pi": math.pi, "e": math.e, "tau": math.tau}

    def evaluate(self, expression):
        if not expression or len(expression) > 500:
            raise ValueError("Invalid expression length")
        value = self._eval(ast.parse(expression.strip(), mode="eval").body)
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ValueError("Expression did not produce a finite number")
        return value

    def _eval(self, node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name) and node.id in self.CONST:
            return self.CONST[node.id]
        if isinstance(node, (ast.List, ast.Tuple)):
            return [self._eval(x) for x in node.elts]
        if isinstance(node, ast.UnaryOp) and type(node.op) in self.UNARY:
            return self.UNARY[type(node.op)](self._eval(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in self.BIN:
            a, b = self._eval(node.left), self._eval(node.right)
            if isinstance(a, list) or isinstance(b, list):
                raise ValueError("Lists cannot be used in arithmetic")
            if type(node.op) is ast.Pow and abs(float(b)) > 1000:
                raise ValueError("Exponent too large")
            return self.BIN[type(node.op)](a, b)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            fn = self.FUNCS.get(node.func.id)
            if fn is None or node.keywords:
                raise ValueError("Function is not allowed")
            return fn(*[self._eval(x) for x in node.args])
        raise ValueError("Unsupported expression")

CALCULATOR = SafeCalculator()

TOOL_SCHEMAS = [{
    "type": "function",
    "function": {
        "name": "calculate",
        "description": "Safely evaluate arithmetic, percentages, powers, roots, trigonometry, logarithms and basic statistics.",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Mathematical expression"}
            },
            "required": ["expression"]
        }
    }
}]

def execute_tool(name, arguments):
    if name != "calculate":
        raise ValueError("Unknown tool")
    return str(CALCULATOR.evaluate(arguments["expression"]))
