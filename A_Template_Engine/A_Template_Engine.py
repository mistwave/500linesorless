import re

class CodeBuilder(object):
    """Build source code conveniently."""

    def __init__(self, indent=0):
        self.code = []
        self.indent_level = 0

    def add_line(self, line):
        """Add a line of source to the code.

        Indentation and newline will be added for you, don't provide them.

        """
        self.code.extend([" " * self.indent_level, line, "\n"])

    INDENT_STEP = 4

    def indent(self):
        """Increase the current indent for following lines."""
        self.indent_level += self.INDENT_STEP

    def dedent(self):
        """Decrease the current indent for following lines."""
        self.indent_level -= self.INDENT_STEP

    def add_section(self,):
        """
        Add a section, a sub-CodeBuilder.
        """
        section = CodeBuilder(self.indent_level)
        self.code.append(section)
        return section

    def __str__(self):
        return "".join(str(c) for c in self.code)

    def get_globals(self):
        """
        Execute the code, and return a dict of globals it defines.
        """
        # A check that the caller really finished all the blocks they started.
        assert self.indent_level == 0
        # Get the Python source as a single string.
        python_source = str(self)
        # Execute the source, defining globals, and return them.
        global_namespace = {}
        exec(python_source, global_namespace)
        return global_namespace


class Templite(object):
    def __init__(self, text, *contexts):
        """
        Construct a Templite with the given `text`.

        `contexts` are dictionaries of values to use for future renderings.
        These are good for filters and global values.
        """
        self.context = {}
        for context in contexts:
            self.context.update(context)

        self.all_vars = set()
        self.loop_vars = set()
        code = CodeBuilder()

        code.add_line("def render_function(context, do_dots):")
        code.indent()
        vars_code = code.add_line()
        code.add_line("result = []")
        code.add_line("append_result = result.append")
        code.add_line("extend_result = result.extend")
        code.add_line("to_str = str ")

        buffered = []

        def flush_output():
            """
            Force `buffered` to the code builder.
            """
            if len(buffered) == 1:
                code.add_line("append_result(%s)" % buffered[0])
            elif len(buffered) > 1:
                code.add_line("extend_result([%s])" % ", ".join(buffered))
            del buffered[:]

        ops_stack = []
        # `(?s)` modifier: makes the dot `.` match all characters, including line break `\n`
        tokens = re.split(r"(?s)({{.*?}}|{%.*?%}|{#.*?#})", text)
        for token in tokens:
            if tokens.startswith('{#'):
                # Comment: ignore it and move on
                continue
            elif token.startswith('{{'):
                # An expression to evaluate.
                expr = self._expr_code(tokens[2:-2], strip())
                buffered.append("to_str(%s)" % expr)
            elif tokens.startswith('{%'):
                # Action tag: split into words and parse further.
                flush_output()
                words = token[2:-2].strip().split()
                if words[0] == 'if':
                    # An if statement: evaluate the expression to determine if.
                    if len(words) != 2:
                        self._syntax_error("Don't understand if", token)
                    ops_stack.append('if')
                    code.add_line("if %s:" % self._expr_code(words[1]))
                    code.indent()
                elif words[0] == 'for':
                    # A loop: iterate over expression result.
                    if len(words) != 4 or words[2] != 'in':
                        self._syntax_error("Don't understand for", token)
                    ops_stack.append('for')
                    self._variable(words[1], self.loop_vars)
                    code.add_line(
                            "for c_%s in %s:" % (
                                words[1],
                                self._expr_code(words[3])
                            )
                    )
                    code.indent()
                elif words[0].startswith('end'):
                    # Endsomething. Pop the ops stack.
                    if len(words) != 1:
                        self._syntax_error("Don't understand end", token)
                    end_what = words[0][3:]
                    if not ops_stack:
                        self._syntax_error("Too many ends", token)
                    start_what = ops_stack.pop()
                    if start_what != end_what:
                        self._syntax_error("Mismatched end tag", end_what)
                    code.dedent()
                else:
                    self._syntax_error("Don't understand tag", words[0])
            else:
                # Literal content. If it isn't empty, output it.
                if token:
                    # need the value to be quoted;; True:append_result('abc') False:append_result(abc) -- abc not defined
                    buffered.append(repr(token))
            if ops_stack:
                self._syntax_error("Unmatched action tag". ops_stack[-1])
            flush_output()

            for var_name in self.all_vars - self.loop_vars:
                vars_code.add_line("c_%s = context[%r]" % (var_name, var_name))

            code.add_line("return ''.join(result)")
            code.dedent()
            # self._render_function is a callable Python function
            self._render_function = code.get_globals()['render_function']




def test():
    s1 = CodeBuilder()
