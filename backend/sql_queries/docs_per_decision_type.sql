SELECT DISTINCT ON (cd.decision_type_id, to_char(publish_timestamp, 'YYYY-MM'))
    cd.id AS decision_id,
    cd.document_url AS document_url,
    cd.created_at AS decision_created_at,
    cd.decision_type_id,
    cd.publish_timestamp,
    cd.amount,
    cat.uid AS acttype_id,
    cat.label AS acttype_name
FROM
    core_decision cd
JOIN
    core_acttype cat ON cd.decision_type_id = cat.uid
WHERE
    cd.created_at > '2025-05-03'
ORDER BY
    cd.decision_type_id,
    to_char(publish_timestamp, 'YYYY-MM'),
    cd.amount DESC NULLS FIRST;