"""Go runtime-support shims, emitted only when the program uses them.

Each entry is (imports it needs, source).  ``__concat`` prints bools as
``true``/``false`` via fmt.Sprint, matching the course's printf.
"""

SHIMS: dict[str, tuple[tuple[str, ...], str]] = {
    "scanf": (("bufio", "os", "strconv"), '''\
var __in = bufio.NewReader(os.Stdin)

func __scanf() int {
\tline, _ := __in.ReadString('\\n')
\tfor len(line) > 0 && (line[len(line)-1] == '\\n' || line[len(line)-1] == '\\r') {
\t\tline = line[:len(line)-1]
\t}
\tvalue, _ := strconv.Atoi(line)
\treturn value
}'''),
    "concat": (("fmt",), '''\
func __concat(parts ...any) string {
\tout := ""
\tfor _, part := range parts {
\t\tout += fmt.Sprint(part)
\t}
\treturn out
}'''),
    "pow": ((), '''\
func __pow(base, exp int) int {
\tresult := 1
\tfor i := 0; i < exp; i++ {
\t\tresult *= base
\t}
\treturn result
}'''),
    "fact": ((), '''\
func __fact(n int) int {
\tif n < 0 {
\t\tpanic("factorial of negative number")
\t}
\tresult := 1
\tfor i := 2; i <= n; i++ {
\t\tresult *= i
\t}
\treturn result
}'''),
    "tern": ((), '''\
func __tern(cond bool, a, b int) int {
\tif cond {
\t\treturn a
\t}
\treturn b
}'''),
    "str": (("fmt",), '''\
func __str(value any) string {
\treturn fmt.Sprint(value)
}'''),
    "b2i": ((), '''\
func __b2i(value bool) int {
\tif value {
\t\treturn 1
\t}
\treturn 0
}'''),
    # casts take any: the course's (int) of a float ROUNDS (6.6 -> 7)
    "toInt": (("math",), '''\
func __toInt(value any) int {
\tswitch v := value.(type) {
\tcase float64:
\t\treturn int(math.Round(v))
\tdefault:
\t\treturn v.(int)
\t}
}'''),
    "toFloat": (("strconv",), '''\
func __toFloat(value any) float64 {
\tswitch v := value.(type) {
\tcase int:
\t\treturn float64(v)
\tcase string:
\t\tparsed, _ := strconv.ParseFloat(v, 64)
\t\treturn parsed
\tdefault:
\t\treturn v.(float64)
\t}
}'''),
    "toBool": ((), '''\
func __toBool(value any) bool {
\tswitch v := value.(type) {
\tcase float64:
\t\treturn v != 0
\tcase int:
\t\treturn v != 0
\tdefault:
\t\treturn v.(bool)
\t}
}'''),
}
