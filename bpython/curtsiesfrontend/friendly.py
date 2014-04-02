class NotImplementedError(NotImplementedError):
    def __init__(self, msg=None):
        if msg is None:
            super(NotImplementedError, self).__init__("Implement it and submit a pull request!")
        else:
            super(NotImplementedError, self).__init__(msg)
