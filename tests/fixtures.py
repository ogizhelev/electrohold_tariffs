"""A representative snapshot of the Electrohold tariff table.

Only the structure relevant to parsing is reproduced: a table whose rows
contain the Bulgarian day/night labels and euro-denominated prices. The
surrounding markup mirrors what the live page emits (extra cells, thin spaces,
comma decimal separators).
"""

TARIFF_PAGE_HTML = """
<html>
  <body>
    <h1>Цени</h1>
    <table>
      <thead>
        <tr><th>Компонента</th><th>Цена</th></tr>
      </thead>
      <tbody>
        <tr><td>Дневна енергия</td><td>0,12854 €/кВтч</td></tr>
        <tr><td>Нощна енергия</td><td>0,07660 €/кВтч</td></tr>
        <tr><td>Друго</td><td>1,50 €</td></tr>
      </tbody>
    </table>
  </body>
</html>
"""

# A page missing the night row, used to exercise the parse-error path.
INCOMPLETE_PAGE_HTML = """
<html><body><table>
  <tr><td>Дневна</td><td>0,12854 €</td></tr>
</table></body></html>
"""
