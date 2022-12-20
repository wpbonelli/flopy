# all code due to Scott Boyce.



import inspect


# decorator approach


def set_supported_kwargs(*keywords: str):
    def decorate(func):
        setattr(func, 'supported_kwargs', set(keywords))
        return func

    return decorate


def kwargs_check(kwargs: dict, supported_kwargs: set[str], disable_future_checks=None):
    if 'kwargs_check' not in kwargs or kwargs['kwargs_check']:
        bad_kwargs = {kw for kw in kwargs if kw not in supported_kwargs}
        bad_kwargs.discard('kwargs_check')

        if bad_kwargs:
            bad_kwargs = '\n"' + '"\n"'.join(sorted(bad_kwargs)) + '"\n'
            raise TypeError(f"Invalid keyword argument(s):{bad_kwargs}")

        if disable_future_checks is not None:
            kwargs['kwargs_check'] = not disable_future_checks



@set_supported_kwargs('kwarg1', 'kwarg2', 'kwarg3')
def util_func(**kwargs):
    kwargs_check(kwargs, util_func.supported_kwargs)
    kwargs['kwargs_check'] = False  # Manually disable future checks
    #
    # Do Stuff
    #
    return


@set_supported_kwargs('kwarg1', 'kwarg2', *util_func.supported_kwargs)
def util_func2(**kwargs):
    kwargs_check(kwargs, util_func2.supported_kwargs, disable_future_checks=True)
    #
    # kwargs['kwargs_check'] = False  # is set from disable_future_checks
    #
    # Do Stuff
    #
    util_func(**kwargs)
    #
    return


@set_supported_kwargs('foofighter1', 'foofighter2', *util_func.supported_kwargs, *util_func2.supported_kwargs)
def foo(**kwargs):
        kwargs_check(kwargs, foo.supported_kwargs, disable_future_checks=True)


class MinorClass:
    # Have to define all dunder methods as class attributes
    init_kwargs = {'relative_path', 'no_open', 'binary'} | util_func.supported_kwargs

    def __init__(self, file, **kwargs):
        kwargs_check(kwargs, MinorClass.init_kwargs, disable_future_checks=True)
        #
        # do stuff
        #
        util_func(**kwargs)

    # Any regular methods can use the decorator
    @set_supported_kwargs('foo1', 'foo2', 'foo3', *util_func2.supported_kwargs)
    def foo(self, **kwargs):
        kwargs_check(kwargs, self.foo.supported_kwargs, disable_future_checks=True)
        #
        # do stuff
        #
        util_func2(**kwargs)
        #
        return

    # This one I am unsure about cause you cannot reference self.foo or MinorClass.foo
    # It seems to work with just foo, but might cause issues with a global foo function
    #    or at least no way to access global foo.
    # You could also make a class attribute that has all of fighter's accepted keywords
    @set_supported_kwargs('f1', 'f2', 'f3', *foo.supported_kwargs, *util_func2.supported_kwargs)
    def fighter(self, **kwargs):
        kwargs_check(kwargs, self.fighter.supported_kwargs, disable_future_checks=True)
        #
        # do stuff
        #
        self.foo(**kwargs)
        util_func2(**kwargs)
        #
        return


def test_decorator_approach():
    util_func(kwarg1=1)
    try:
        util_func(kwarg9=1)
    except TypeError:
        print("util_func(kwarg9=1)  failed as expected")

    util_func2(kwarg1=1)
    try:
        util_func2(kwarg9=1)
    except TypeError:
        print("util_func2(kwarg9=1) failed as expected")

    x = MinorClass('hello')
    x.foo(foo1=55)
    try:
        x.foo(foot1=55)
    except TypeError:
        print("x.foo(foot1=55) failed as expected")

    x.fighter(foo1=55)
    try:
        x.fighter(foot1=55)
    except TypeError:
        print("x.fighter(foot1=55) failed as expected")



# object oriented approach


class KeywordTracker:
    unpacked_flag: str = '_KeywordTracker'

    function: str
    exception_for_unused: bool
    _kwargs: dict
    _not_used: dict

    def __init__(self, *, _kwargs: dict, _exception_for_unused: bool):
        self.function = inspect.stack()[2].function
        self.exception_for_unused = _exception_for_unused

        self._kwargs = _kwargs.copy()
        self._not_used = {k: True for k in _kwargs}

    @classmethod
    def init(cls, kwargs, exception_for_unused=True):
        if not isinstance(kwargs, cls):  # Not KeywordTracker instance
            if cls.unpacked_flag in kwargs:
                # self = kwargs.pop(cls.unpacked_flag)
                return cls.init(kwargs[cls.unpacked_flag], exception_for_unused)
            else:
                return cls(_kwargs=kwargs, _exception_for_unused=exception_for_unused)

        return kwargs

    def get_unused(self):
        return [k for k in self._not_used if self._not_used[k]]

    def check_usage(self, force_check=False):
        if not self.exception_for_unused and not force_check:
            return

        if force_check or self.function == inspect.stack()[1].function:
            bad_kwargs = self.get_unused()
            if bad_kwargs:
                bad_kwargs = '\n"' + '"\n"'.join(sorted(bad_kwargs)) + '"\n'
                raise TypeError(f"Invalid or unused keyword argument(s):{bad_kwargs}")

    def get_keys(self, set_as_used=False):
        if set_as_used:
            self._not_used = {k: False for k in self._kwargs}
        return self._kwargs.keys()

    def set_as_used(self, key):
        if isinstance(key, str):
            key = [key]

        for k in key:
            if k in self._not_used:
                self._not_used[k] = False

    def get(self, key, set_as_used=True):
        if isinstance(key, str):
            return self.get_value(key, set_as_used)
        return self.get_dict(key, set_as_used)

    def get_value(self, key, set_as_used=True):
        if set_as_used:
            return self[key]
        return self._kwargs[key]

    def get_dict(self, keys, set_as_used=True):
        if set_as_used:
            return {k: self[k] for k in keys}
        return {k: self._kwargs[k] for k in keys}

    def pop(self, keys):  # Warning, this deletes the keyword for all levels of **kwargs
        if isinstance(keys, str):
            del self._not_used[keys]
            return self._kwargs.pop(keys)

        for k in keys:
            del self._not_used[k]
        return {k: self._kwargs.pop(k) for k in keys}

    def check_keywords(self, supported_keywords, force_check=False, raise_exception=False):
        if force_check or self.function == inspect.stack()[1].function:
            bad_kwargs = {kw for kw in self._kwargs if kw not in supported_keywords}

            if bad_kwargs and raise_exception:
                bad_kwargs = '\n"' + '"\n"'.join(sorted(bad_kwargs)) + '"\n'
                raise TypeError(f"Invalid keyword argument(s):{bad_kwargs}")

            return sorted(bad_kwargs)

        return []

    def keys(self):  # Do not use, only for unpacking object with func(**kwargs)
        return self.unpacked_flag,  # Returns as tuple(unpacked_flag)

    def __getitem__(self, item):
        if item == self.unpacked_flag:  # Flag to indicate passing as **KeywordTracker
            return self

        if item not in self._kwargs:
            raise KeyError(f'Missing keyword argument: "{item}"')

        self._not_used[item] = False
        return self._kwargs[item]

    def __setitem__(self, key, value):
        self._kwargs[key] = value
        if key not in self._not_used:
            self._not_used[key] = True

    def __contains__(self, item):
        return item in self._kwargs

    def __delitem__(self, key):
        del self._kwargs[key]
        del self._not_used[key]

    def __repr__(self):
        return f'{self.__class__.__name__}({self._kwargs})'

    def __str__(self):
        return repr(self)

    def __len__(self):
        return len(self._kwargs)


def method_4(**kwargs):
    kwargs = KeywordTracker.init(kwargs)
    m4_kw = kwargs["m4"]
    kwargs.check_usage()

def method_3(**kwargs):
    kwargs = KeywordTracker.init(kwargs)
    m3_kw = kwargs["m3"]
    kwargs.check_usage()

def method_2(**kwargs):
    kwargs = KeywordTracker.init(kwargs)
    m2_kw = kwargs["m2"]
    if m2_kw:
        method_3(**kwargs)
    else:
        method_4(**kwargs)
    kwargs.check_usage()

def method_1(**kwargs):
    kwargs = KeywordTracker.init(kwargs)
    method_2(**kwargs)
    kwargs.check_usage()


def test_object_approach():
    method_1(m1="1", m2=True, m3="2")
    method_1(m1="1", m2=False, m3="2")


def create_obj(**kwargs):
    print(type(kwargs))
    print(kwargs)
    kwargs = KeywordTracker.init(kwargs)
    print('a' in kwargs)
    x = kwargs['a']
    _ = x
    return test2(**kwargs)


def test2(**kwargs):
    kwargs = KeywordTracker.init(kwargs)
    x = kwargs['b']
    _ = x
    
    x = KeywordTracker.init({'a': 55, 'b': 99})
    x2 = create_obj(**x)
