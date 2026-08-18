UPDATE exercise_mappings
SET primary_muscle = 'Shoulders', updated_at = CURRENT_TIMESTAMP
WHERE primary_muscle = 'Delts';

UPDATE exercise_mappings
SET secondary_muscle = 'Shoulders', updated_at = CURRENT_TIMESTAMP
WHERE secondary_muscle = 'Delts';
