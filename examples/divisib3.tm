alphabet = [0, 1]
start = q0
accept = qaccept
reject = qreject
null = _


(q0, 0) => (q0, 0, >)
(q0, 1) => (q1, 1, >)
(q0, _) => (qaccept, _, _)

(q1, 0) => (q2, 0, >)
(q1, 1) => (q0, 1, >)
(q1, _) => (qreject, _, _)

(q2, 0) => (q1, 0, >)
(q2, 1) => (q2, 1, >)
(q2, _) => (qreject, _, _)