# Witica.util

Contains various helper functions.

## Attributes
* `timeUnits`: contains a dictionary that maps different time units to seconds. Usage of for example `Witica.util.timeUnits.hour` gives the value 3600. The available keys are `second, minute, 	hour, 	day, week, month, year`,

## getHumanReadableDate()

**Syntax:**

	getHumanReadableDate(date)

Returns a string representation for the given date. If the date is not longer than one week ago, the string will contain a relative description as for example “3 days ago”.

The function takes the following arguments:

* `date`: the date to be formatted.

## shorten()

**Syntax:**

	shorten(html, maxLength)

Returns a shortened plain text version of a given maximal length for the given html content. The function tries to preferably not break sentences or words.

The function takes the following arguments:

* `html`: the html content to be shortened,
* `maxLength`: the maximum length of the shortened version.

## getYCoord()

**Syntax:**

	getYCoord(element)

Returns the y-coordinate of a DOM element on the webpage.

The function takes the following arguments:

* `element`: the element which y coordinate should be calculated. 