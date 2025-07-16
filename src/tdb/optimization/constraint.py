from enum import Enum


class TDBMetric(Enum):
    ERROR, FEEDBACK, RUNTIME = range(3)


class TDBConstraint:
    def __init__(self, metric, threshold, weight):
        if metric == 'error':
            self.metric = TDBMetric.ERROR
        elif metric == 'feedback':
            self.metric = TDBMetric.FEEDBACK
        elif metric == 'runtime':
            self.metric = TDBMetric.RUNTIME
        else:
            raise ValueError(f'Invalid constraint metric: {metric}')
        self.threshold = threshold
        self.weight = weight

    def __repr__(self):
        return f'({self.metric.name.lower()}, {self.threshold}, {self.weight})'
    
    def cost(self, error, nr_feedbacks, runtime):
        if self.metric == TDBMetric.ERROR:
            return runtime + self.weight * nr_feedbacks
        elif self.metric == TDBMetric.FEEDBACK:
            return runtime + self.weight * error
        elif self.metric == TDBMetric.RUNTIME:
            return nr_feedbacks + self.weight * error
        
    def satisfies(self, error, nr_feedbacks, runtime, nr_nl_filters):
        # (Different from check_continue) Check if the constraint is satisfied.
        if self.metric == TDBMetric.ERROR:
            return error <= self.threshold
        elif self.metric == TDBMetric.FEEDBACK:
            return nr_feedbacks <= self.threshold * nr_nl_filters
        elif self.metric == TDBMetric.RUNTIME:
            return runtime <= self.threshold

    def check_continue(self, error, nr_feedbacks, runtime, nr_nl_filters):
        # Error decreases while feedbacks and runtime increase.
        if self.metric == TDBMetric.ERROR:
            return error > self.threshold
        elif self.metric == TDBMetric.FEEDBACK:
            return nr_feedbacks < self.threshold * nr_nl_filters and error > 0
        elif self.metric == TDBMetric.RUNTIME:
            return runtime < self.threshold and error > 0
