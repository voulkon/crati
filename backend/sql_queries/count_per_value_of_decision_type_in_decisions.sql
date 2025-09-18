SELECT decision_type_id, COUNT(*)
FROM core_decision
GROUP BY decision_type_icord
ORDER BY COUNT(*) DESC;