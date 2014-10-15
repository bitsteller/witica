# Witica.util.Event

Represents an event that listeners can subscribe to in order to get notified when the event is fired.

## Attributes
This prototype has no attributes.

## Event() (Constructor)

**Syntax:**

	Event()

Creates a new event object.

The function takes no arguments.

## Event.addListener()

**Syntax:**

	Event.addListener(context, callable)

Adds a listener to the event that will be called when the event is fired. The `callable` object will be called with the given `context`. If the event is fired with arguments those arguments will be passed to `callable`.

The function takes the following arguments:

* `context`: the context in which the callable will be called when the event is fired,
* `callable`: the function that should be called when the event is fired.

## Event.removeListener()

**Syntax:**

	Event.removeListener(context, callable)

Removes the listener, so that it is no longer called when the event is fired. Note that the listener will only be successfully removed, if the `Event.addListener()` function was previously called with the exact same pair of `context` and `callable` arguments.

The function takes the following arguments:

* `context`: the context that was passed when `Event.addListener()` was called,
* `callable`: the callable that was passed when `Event.addListener()` was called and should no longer be called when the event is fired.

## Event.fire()

**Syntax:**

	Event.fire(argument)

Calls all currently registered listeners of the event with the argument given to this function.

The function takes the following arguments:

* `argument`: an optional argument that is passed to all listeners.

## Event.getNumberOfListeners()

**Syntax:**

	Event.getNumberOfListeners()

Returns the number of currently registered listeners for this event.

The function takes the no arguments.

