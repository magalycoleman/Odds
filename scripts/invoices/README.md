# TBI invoice check scripts (daily-email-sweep item 14)

- `parse_invoice.py <zip> <outdir>`: takes "INVOICE <no.>.zip", saves `<no.>.pdf`, prints invoice no., date, container, boxes, total, lines (PO, style, color, Reg/B&T, qty, price) and `sum_check` (sum of the lines). If `sum_check` differs from the stated total, the invoice total is wrong.
- `thread_info.py <get_message output files...>`: lists the invoice zips (attachment index) and the dates of Damary's DUCA / shipping documents messages in a forwarded booking thread.
- `compare.py <wip.json> <invoice json dir> <exported.json> <out.json>`: matches invoice lines to WIP lines (PO No + Style No + Color) and builds Invoice Qty, Invoice Mistakes (short/over %, invoiced vs cut, price rule) and the dated Flag Email Notes line.

Run Python with `-I`. Added November 26, 2026.
