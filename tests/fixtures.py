"""Representative snapshots of the Electrohold tariff table for parser tests.

The real page lays each tariff row out as:
  [metering method] [day/night zone] [energy price] [FINAL price incl. network
  services] — both prices WITHOUT VAT.
These fixtures reproduce that structure (and variations of it) so the parser's
header-driven column selection and its fallbacks can be exercised in isolation.
"""

# Mirrors the live page: energy column first, final column second, and a
# rowspan-style empty leading cell on the night row.
TARIFF_PAGE_HTML = """
<html><body>
  <table>
    <thead>
      <tr>
        <th>Начин на измерване</th><th>Зони в денонощието</th>
        <th>Цена за електрическа енергия</th>
        <th>Крайни цени за електрическа енергия с включени мрежови услуги</th>
      </tr>
    </thead>
    <tbody>
      <tr><td>С две скали</td><td>Дневна</td><td>0,09297 €/кВтч</td><td>0,12854 €/кВтч</td></tr>
      <tr><td></td><td>Нощна</td><td>0,04103 €/кВтч</td><td>0,07660 €/кВтч</td></tr>
    </tbody>
  </table>
</body></html>
"""

# Same structure but the energy base price has risen ABOVE the day final price's
# old magnitude bound (> 0.10). A magnitude-based parser would wrongly pick the
# energy column; a header-driven one still picks the final column.
RISEN_BASE_PAGE_HTML = """
<html><body>
  <table>
    <tr>
      <th>Зони</th><th>Цена за електрическа енергия</th>
      <th>Крайни цени с включени мрежови услуги</th>
    </tr>
    <tr><td>Дневна</td><td>0,15000 €/кВтч</td><td>0,20000 €/кВтч</td></tr>
    <tr><td>Нощна</td><td>0,11000 €/кВтч</td><td>0,16000 €/кВтч</td></tr>
  </table>
</body></html>
"""

# A future layout that adds a VAT-inclusive column to the right. The parser must
# still pick the non-VAT final column (so the ×VAT multiplier is applied once).
WITH_VAT_COLUMN_PAGE_HTML = """
<html><body>
  <table>
    <tr>
      <th>Зони</th><th>Цена за електрическа енергия</th>
      <th>Крайни цени с включени мрежови услуги</th>
      <th>Крайни цени с ДДС</th>
    </tr>
    <tr><td>Дневна</td><td>0,09297 €/кВтч</td><td>0,12854 €/кВтч</td><td>0,15425 €/кВтч</td></tr>
    <tr><td>Нощна</td><td>0,04103 €/кВтч</td><td>0,07660 €/кВтч</td><td>0,09192 €/кВтч</td></tr>
  </table>
</body></html>
"""

# No understandable header (labels stripped): parser must fall back to the
# right-most euro value, which is still the final price.
NO_HEADER_PAGE_HTML = """
<html><body>
  <table>
    <tr><td>Дневна</td><td>0,09297 €/кВтч</td><td>0,12854 €/кВтч</td></tr>
    <tr><td>Нощна</td><td>0,04103 €/кВтч</td><td>0,07660 €/кВтч</td></tr>
  </table>
</body></html>
"""

# Missing the night row entirely, used to exercise the parse-error path.
INCOMPLETE_PAGE_HTML = """
<html><body><table>
  <tr><th>Зони</th><th>Крайни цени с включени мрежови услуги</th></tr>
  <tr><td>Дневна</td><td>0,12854 €/кВтч</td></tr>
</table></body></html>
"""
