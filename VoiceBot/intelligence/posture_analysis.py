"""Describe visible posture over a session. No confidence, emotion, personality or medical claim."""

NAMES = ('slouching', 'head_position', 'shoulder_alignment', 'body_orientation')
CUES = {
    'slouching': 'Sitting or standing a little taller, with your back away from the chair, may help you look more open.',
    'head_position': 'Keeping your head level, with the camera near eye height, may help.',
    'shoulder_alignment': 'Letting your shoulders settle level with each other may help.',
    'body_orientation': 'Turning your body toward the camera may help.',
}
MINIMUM_SAMPLES = 3
TREND_SAMPLES = 6
TREND_CHANGE = 8


def summarise(samples):
    """samples: ordered (slouching, head, shoulders, orientation) values, each 0-100 where higher is better."""
    samples = [sample for sample in samples if all(isinstance(value, (int, float)) for value in sample)]
    if len(samples) < MINIMUM_SAMPLES:
        return {'available': False, 'samples': len(samples),
                'note': 'Too few clear camera samples for feedback. This does not count against you.'}
    indicators = []
    middle = len(samples) // 2
    for index, name in enumerate(NAMES):
        values = [sample[index] for sample in samples]
        average = sum(values) / len(values)
        trend = 'not enough samples'
        if len(samples) >= TREND_SAMPLES:
            change = sum(values[middle:]) / len(values[middle:]) - sum(values[:middle]) / len(values[:middle])
            trend = 'improved' if change >= TREND_CHANGE else 'dropped' if change <= -TREND_CHANGE else 'steady'
        indicators.append({'name': name, 'average': round(average, 1), 'trend': trend, 'steady_share': round(100 * sum(value >= 70 for value in values) / len(values)),
                           'cue': CUES[name] if average < 70 or trend == 'dropped' else None})
    focus = min(indicators, key=lambda item: item['average'])
    return {'available': True, 'samples': len(samples), 'indicators': indicators, 'focus': focus['name'] if focus['cue'] else None,
            'note': 'These describe what the camera could see, and are affected by camera angle, lighting and individual differences. They are not a judgement of you, and they do not change your proficiency.'}
