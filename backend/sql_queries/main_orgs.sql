SELECT uid, label
FROM core_organization
WHERE label LIKE 'ΥΠΟΥΡΓΕΙΟ%'
   OR label LIKE 'ΔΗΜΟΣ%'
   OR label LIKE 'ΠΕΡΙΦΕΡΕΙΑ%'
ORDER by label desc;
