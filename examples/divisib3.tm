alphabet = [0, 1]
start = q0
accept = qa
reject = qr
null = _

(q0, 0) => (q0, 0, <)
(q0, 1) => (q0, 1, <)
(q0, _) => (q0, 1, <)