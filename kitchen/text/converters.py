# -*- coding: utf-8 -*-
#
# Copyright (c) 2010 Red Hat, Inc.
#
# kitchen is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# kitchen is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with kitchen; if not, see <http://www.gnu.org/licenses/>
#
# Authors:
#   Toshio Kuratomi <toshio@fedoraproject.org>
#   Seth Vidal
#
# Portions of code taken from yum/i18n.py and
# python-fedora: fedora/textutils.py

'''
Functions to handle conversion of byte :class:`str` and :class:`unicode`
strings.

.. versionchanged:: kitchen 0.2a2 ; API kitchen.text 1.1.0
    Added :func:`~kitchen.text.converters.getwriter`
'''
try:
    from base64 import b64encode, b64decode
except ImportError:
    from kitchen.pycompat24.base64 import b64encode, b64decode

import codecs
import warnings
import xml.sax.saxutils

from kitchen import _, b_
from kitchen.pycompat24 import sets
sets.add_builtin_set()

from kitchen.text.exceptions import ControlCharError, XmlEncodeError
from kitchen.text.misc import guess_encoding, html_entities_unescape, \
        process_control_chars

#: Aliases for the utf-8 codec
_UTF8_ALIASES = frozenset(('utf-8', 'UTF-8', 'utf8', 'UTF8', 'utf_8', 'UTF_8',
    'utf', 'UTF', 'u8', 'U8'))
#: Aliases for the latin-1 codec
_LATIN1_ALIASES = frozenset(('latin-1', 'LATIN-1', 'latin1', 'LATIN1',
    'latin', 'LATIN', 'l1', 'L1', 'cp819', 'CP819', '8859', 'iso8859-1',
    'ISO8859-1', 'iso-8859-1', 'ISO-8859-1'))

def to_unicode(obj, encoding='utf-8', errors='replace', nonstring=None,
        non_string=None):
    '''Convert an object into a :class:`unicode` string

    :arg obj: Object to convert to a :class:`unicode` string.  This should
        normally be a byte :class:`str`
    :kwarg encoding: What encoding to try converting the byte :class:`str` as.
        Defaults to :term:`utf-8`
    :kwarg errors: If errors in decoding are found, perform this action.
        Defaults to ``replace`` which replaces the invalid bytes with
        a character that means the bytes were unable to be decoded.  Other
        values are the same as the error handling schemes in the `codec base
        classes
        <http://docs.python.org/library/codecs.html#codec-base-classes>`_.
        For instance ``strict`` which raises an exception and ``ignore`` which
        simply omits the non-decodable characters.
    :kwarg nonstring: How to treat nonstring values.  Possible values are:

        :simplerepr: Attempt to call the object's "simple representation"
            method and return that value.  Python-2.3+ has two methods that
            try to return a simple representation: :meth:`object.__unicode__`
            and :meth:`object.__str__`.  We first try to get a usable value
            from :meth:`object.__unicode__`.  If that fails we try the same
            with :meth:`object.__str__`.
        :empty: Return an empty :class:`unicode` string
        :strict: Raise a :exc:`TypeError`
        :passthru: Return the object unchanged
        :repr: Attempt to return a :class:`unicode` string of the repr of the
            object

        Default is ``simplerepr``

    :kwarg non_string: *Deprecated* Use :attr:`nonstring` instead
    :raises TypeError: if :attr:`nonstring` is ``strict`` and
        a non-:class:`basestring` object is passed in or if :attr:`nonstring`
        is set to an unknown value
    :raises UnicodeDecodeError: if :attr:`errors` is ``strict`` and
        :attr:`obj` is not decodable using the given encoding
    :returns: :class:`unicode` string or the original object depending on the
        value of :attr:`nonstring`.

    Usually this should be used on a byte :class:`str` but it can take both
    byte :class:`str` and :class:`unicode` strings intelligently.  Nonstring
    objects are handled in different ways depending on the setting of the
    :attr:`nonstring` parameter.

    The default values of this function are set so as to always return
    a :class:`unicode` string and never raise an error when converting from
    a byte :class:`str` to a :class:`unicode` string.  However, when you do
    not pass validly encoded text (or a nonstring object), you may end up with
    output that you don't expect.  Be sure you understand the requirements of
    your data, not just ignore errors by passing it through this function.

    .. versionchanged:: 0.2.1a2
        Deprecated :attr:`non_string` in favor of :attr:`nonstring` parameter and changed
        default value to ``simplerepr``
    '''
    if isinstance(obj, basestring):
        if isinstance(obj, unicode):
            return obj
        if encoding in _UTF8_ALIASES:
            return unicode(obj, 'utf-8', errors)
        if encoding in _LATIN1_ALIASES:
            return unicode(obj, 'latin-1', errors)
        return obj.decode(encoding, errors)

    if non_string:
        warnings.warn(b_('non_string is a deprecated parameter of'
            ' to_unicode().  Use nonstring instead'), DeprecationWarning,
            stacklevel=2)
        if not nonstring:
            nonstring = non_string

    if not nonstring:
        nonstring = 'simplerepr'
    if nonstring == 'empty':
        return u''
    elif nonstring == 'passthru':
        return obj
    elif nonstring == 'simplerepr':
        try:
            simple = obj.__unicode__()
        except AttributeError:
            simple = None
        if not simple:
            try:
                simple = str(obj)
            except UnicodeError:
                try:
                    simple = obj.__str__()
                except (UnicodeError, AttributeError):
                    simple = u''
        if not isinstance(simple, unicode):
            return unicode(simple, encoding, errors)
        return simple
    elif nonstring in ('repr', 'strict'):
        obj_repr = repr(obj)
        if not isinstance(obj_repr, unicode):
            obj_repr = unicode(obj_repr, encoding, errors)
        if nonstring == 'repr':
            return obj_repr
        raise TypeError(_('to_unicode was given "%(obj)s" which is neither'
            ' a byte string (str) or a unicode string') % {'obj': obj_repr})

    raise TypeError(_('nonstring value, %(param)s, is not set to a valid'
        ' action') % {'param': nonstring})

def to_bytes(obj, encoding='utf-8', errors='replace', nonstring=None,
        non_string=None):
    '''Convert an object into a byte :class:`str`

    :arg obj: Object to convert to a byte :class:`str`.  This should normally
        be a :class:`unicode` string.
    :kwarg encoding: Encoding to use to convert the :class:`unicode` string
        into a byte :class:`str`.  **Warning**: if you pass a byte
        :class:`str` into this function the byte :class:`str` is returned
        unmodified.  It is not re-encoded with this encoding.  Defaults to
        :term:`utf-8`.
    :kwarg errors: If errors are found when encoding the string, perform this
        action.  Defaults to 'replace' which replaces the error with a '?'
        character to show a character was unable to be encoded.  Other values
        are those that can be given to the :func:`str.encode`.  For instance
        'strict' which raises an exception and 'ignore' which simply omits the
        non-encodable characters.
    :kwargs nonstring: How to treat nonstring values.  Possible values are:

        :simplerepr: Attempt to call the object's "simple representation"
            method and return that value.  Python-2.3+ has two methods
            that try to return a simple representation: __unicode__() and
            __str__().  We first try to get a usable value from
            __str__().  If that fails we try the same with __unicode__().
        :empty: Return an empty byte string
        :strict: Raise a TypeError
        :passthru: Return the object unchanged
        :repr: Attempt to return a byte string of the repr of the
            object

        Default is ``simplerepr``.

    :kwarg non_string: *Deprecated* Use :attr:`nonstring` instead.
    :raises TypeError: if :attr:`nonstring` is ``strict`` and
        a non-:class:`basestring` object is passed in or if :attr:`nonstring`
        is set to an unknown value.
    :raises UnicodeEncodeError: if :attr:`errors` is ``strict`` and all of the
        bytes of :attr:`obj` are unable to be encoded using :attr:`encoding`.
    :returns: byte :class:`str` or the original object depending on the value
        of :attr:`nonstring`.

    Usually, this should be used on a :class:`unicode` string but it can take
    either a byte :class:`str` or a :class:`unicode` string intelligently.
    Nonstring objects are handled in different ways depending on the setting
    of the :attr:`nonstring` parameter.

    The default values of this function are set so as to always return
    a byte string and never raise an error when converting from unicode to
    bytes.  However, when you do not pass an encoding that can validly encode
    the object (or a non-string object), you may end up with output that you
    don't expect.  Be sure you understand the requirements of your data, not
    just ignore errors by passing it through this function.

    .. versionchanged:: 0.2.1a2
        Deprecated :attr:`non_string` in favor of :attr:`nonstring` parameter
        and changed default value to ``simplerepr``
    '''
    if isinstance(obj, basestring):
        if isinstance(obj, str):
            return obj
        return obj.encode(encoding, errors)
    if non_string:
        warnings.warn(b_('non_string is a deprecated parameter of'
            ' to_bytes().  Use nonstring instead'), DeprecationWarning,
            stacklevel=2)
        if not nonstring:
            nonstring = non_string
    if not nonstring:
        nonstring = 'simplerepr'

    if nonstring == 'empty':
        return ''
    elif nonstring == 'passthru':
        return obj
    elif nonstring == 'simplerepr':
        try:
            simple = str(obj)
        except UnicodeError:
            try:
                simple = obj.__str__()
            except (AttributeError, UnicodeError):
                simple = None
        if not simple:
            try:
                simple = obj.__unicode__()
            except AttributeError:
                simple = ''
        if isinstance(simple, unicode):
            simple = simple.encode(encoding, 'replace')
        return simple
    elif nonstring in ('repr', 'strict'):
        try:
            obj_repr = obj.__repr__()
        except (AttributeError, UnicodeError):
            obj_repr = ''
        if isinstance(obj_repr, unicode):
            obj_repr =  obj_repr.encode(encoding, errors)
        else:
            obj_repr = str(obj_repr)
        if nonstring == 'repr':
            return obj_repr
        raise TypeError(_('to_bytes was given "%(obj)s" which is neither'
            ' a unicode string or a byte string (str)') % {'obj': obj_repr})

    raise TypeError(_('nonstring value, %(param)s, is not set to a valid'
        ' action') % {'param': nonstring})

def to_utf8(obj, errors='replace', non_string='passthru'):
    '''Deprecated.  Use to_bytes(obj, encoding='utf-8', non_string='passthru')

    Convert 'unicode' to an encoded utf-8 byte string
    '''
    warnings.warn(_('kitchen.text.converters.to_utf8 is deprecated.  Use'
        ' kitchen.text.converters.to_bytes(obj, encoding="utf-8",'
        ' nonstring="passthru" instead.'), DeprecationWarning, stacklevel=2)
    return to_bytes(obj, encoding='utf-8', errors=errors,
            nonstring=non_string)

### str is also the type name for byte strings so it's not a good name for
### something that can return unicode strings
def to_str(obj):
    '''Deprecated.

    This function converts something to a byte :class:`str if it isn't one.
    It's used to call :func:`str` or func:`unicode` on the object to get its
    simple representation without danger of getting a :exc:`UnicodeError`.
    You should be using :func:`to_unicode` or :func:`to_bytes` explicitly
    instead.  If you need unicode strings::

        to_unicode(obj, nonstring='simplerepr')

    If you need byte strings::

        to_bytes(obj, nonstring='simplerepr')
    '''
    warnings.warn(_('to_str is deprecated.  Use to_unicode or to_bytes'
        ' instead.  See the to_str docstring for'
        ' porting information.'),
        DeprecationWarning, stacklevel=2)
    return to_bytes(obj, nonstring='simplerepr')

#
# XML Related Functions
#

def unicode_to_xml(string, encoding='utf-8', attrib=False,
        control_chars='replace'):
    '''Take a unicode string and turn it into a byte string suitable for xml

    :arg string: unicode string to encode for return
    :kwarg encoding: encoding to use for the returned byte string.  Default is
        to encode to utf8.  If all the characters in string are not encodable
        in this encoding, the unknown characters will be entered into the output
        string using xml character references.
    :kwarg attrib: If True, quote the string for use in an xml attribute.
        If False (default), quote for use in an xml text field.
    :kwarg control_chars: XML does not allow ASCII control characters.  When
        we encounter those we need to know what to do.  Valid options are:
        :replace: (default) Replace the control characters with "?"
        :ignore: Remove the characters altogether from the output
        :strict: Raise an error when we encounter a control character
    :raises XmlEncodeError: If control_chars is set to 'strict' and the string
        to be made suitable for output to xml contains control characters or if
        :attr:`string` is not a unicode type then we raise this exception.
    :raises ValueError: If control_chars is set to something other than
        replace, ignore, or strict.
    :rtype: byte string
    :returns: representation of the unicode string with any bytes that aren't
        available in xml taken care of.

    XML files consist mainly of text encoded using a particular charset.  XML
    also denies the use of certain bytes in the encoded text (example: ASCII
    Null).  There are also special characters that must be escaped if they are
    present in the input (example: "<").  This function takes care of all of
    those issues for you.

    There are a few different ways to use this function depending on your needs.
    The simplest invocation is like this::

       unicode_to_xml(u'String with non-ASCII characters: <"á と">')

    This will return the following to you, encoded in utf8::

      'String with non-ASCII characters: &lt;"á と"&gt;'

    Pretty straightforward.  Now, what if you need to encode your document in
    something other than utf8?  For instance, latin1?  Let's see::

       unicode_to_xml(u'String with non-ASCII characters: <"á と">', encoding='latin1')
       'String with non-ASCII characters: &lt;"á &#12392;"&gt;'

    Because the "と" character is not available in the latin1 charset, it is
    replaced with a "&#12392;" in our output.  This is an xml character
    reference which represents the character at unicode codepoint 12392, the
    "と" character.

    When you want to reverse this, use :func:`xml_to_unicode` which will turn
    a byte string to unicode and replace the xmlcharrefs with the unicode
    characters.

    XML also has the quirk of not allowing ASCII control characters in its
    output.  The control_chars parameter allows us to specify what to do with
    those.  For use cases that don't need absolute character by character
    fidelity (example: holding strings that will just be used for display
    in a GUI app later), the default value of 'replace' works well::

        unicode_to_xml(u'String with disallowed control chars: \u0000\u0007')
        'String with disallowed control chars: ??'

    If you do need to be able to reproduce all of the characters at a later
    date (examples: if the string is a key value in a database or a path on a
    filesystem) you have many choices.  Here are a few that rely on utf7, a
    verbose encoding that encodes control values (as well as all other unicode
    values) to characters from within the ASCII printable characters.  The good
    thing about doing this is that the code is pretty simple.  You just need to
    use utf7 both when encoding the field for xml and when decoding it for use
    in your python program::

        unicode_to_xml(u'String with unicode: と and control char: \u0007', encoding='utf7')
        'String with unicode: +MGg and control char: +AAc-'
        [...]
        xml_to_unicode('String with unicode: +MGg and control char: +AAc-', encoding='utf7')
        u'String with unicode: と and control char: \u0007'

    As you can see, the utf7 encoding will transform even characters that
    would be representable in utf8.  This can be a drawback if you want
    unicode characters in the file to be readable without being decoded first.
    You can work around this with increased complexity in your application
    code::

        encoding = 'utf-8'
        u_string = u'String with unicode: と and control char: \u0007'
        try:
            # First attempt to encode to utf8
            data = unicode_to_xml(u_string, encoding=encoding, errors='strict')
        except XmlEncodeError:
            # Fallback to utf7
            encoding = 'utf7'
            data = unicode_to_xml(u_string, encoding=encoding, errors='strict')
        write_tag('<mytag encoding=%s>%s</mytag>' % (encoding, data))
        [...]
        encoding = tag.attributes.encoding
        u_string = xml_to_unicode(u_string, encoding=encoding)

    Using code similar to that, you can have some fields encoded using your
    default encoding and fallback to utf7 if there are control characters
    present.

    .. seealso::
        :func:`bytes_to_xml`
            if you're dealing with bytes that are non-text or of an unknown
            encoding that you must preserve on a byte for byte level.
        :func:`guess_encoding_to_xml`
            if you're dealing with strings in unknown encodings that you don't
            need to save with char-for-char fidelity.
    '''
    if not string:
        # Small optimization
        return ''
    try:
        process_control_chars(string, strategy=control_chars)
    except TypeError:
        raise XmlEncodeError(_('unicode_to_xml must have a unicode type as'
                ' the first argument.  Use bytes_string_to_xml for byte'
                ' strings.'))
    except ValueError:
        raise ValueError(_('The control_chars argument to unicode_to_xml'
                ' must be one of ignore, replace, or strict'))
    except ControlCharError, exc:
        raise XmlEncodeError(exc.args[0])

    string = string.encode(encoding, 'xmlcharrefreplace')

    # Escape characters that have special meaning in xml
    if attrib:
        string = xml.sax.saxutils.escape(string, entities={'"':"&quot;"})
    else:
        string = xml.sax.saxutils.escape(string)
    return string

def xml_to_unicode(byte_string, encoding='utf-8', errors='replace'):
    '''Transform a byte string from an xml file into unicode

    :arg byte_string: byte string to decode
    :kwarg encoding: encoding that the byte string is in
    :kwarg errors: What to do if not every character is decodable using
        :attr:`encoding`.  See the :func:`to_unicode` docstring for
        legal values.
    :returns: unicode string decoded from :attr:`byte_string`

    This function attempts to reverse what :func:`unicode_to_xml` does.
    It takes a byte string (presumably read in from an xml file) and expands
    all the html entities into unicode characters and decodes the bytes into
    a unicode string.  One thing it cannot do is restore any control
    characters that were removed prior to inserting into the file.  If you
    need to keep such characters you need to use func:`xml_to_bytes` and
    :func:`bytes_to_xml` instead.
    '''
    string = to_unicode(byte_string, encoding=encoding, errors=errors)
    string = html_entities_unescape(string)
    return string

def byte_string_to_xml(byte_string, input_encoding='utf-8', errors='replace',
        output_encoding='utf-8', attrib=False, control_chars='replace'):
    '''Make sure a byte string is validly encoded for xml output

    :arg byte_string: Byte string to make sure is valid xml output
    :kwarg input_encoding: Encoding of byte_string.  Default 'utf-8'
    :kwarg errors: How to handle errors encountered while decoding the
        byte_string into unicode at the beginning of the process.  Values are:

        :replace: (default) Replace the invalid bytes with a '?'
        :ignore: Remove the characters altogether from the output
        :strict: Raise a UnicodeDecodeError when we encounter a non-decodable
            character

    :kwarg output_encoding: Encoding for the xml file that this string will go
        into.  Default is 'utf-8'.  If all the characters in byte_string are
        not encodable in this encoding, the unknown characters will be
        entered into the output string using xml character references.
    :kwarg attrib: If True, quote the string for use in an xml attribute.
        If False (default), quote for use in an xml text field.
    :kwarg control_chars: XML does not allow ASCII control characters.  When
        we encounter those we need to know what to do.  Valid options are:

        :replace: (default) Replace the control characters with "?"
        :ignore: Remove the characters altogether from the output
        :strict: Raise an error when we encounter a control character

    :raises XmlEncodeError: If control_chars is set to 'strict' and the string
        to be made suitable for output to xml contains control characters then
        we raise this exception.
    :raises UnicodeDecodeError: If errors is set to 'strict' and the
        byte_string contains bytes that are not decodable using input_encoding,
        this error is raised
    :rtype: byte string
    :returns: representation of the byte string in the output encoding with
        any bytes that aren't available in xml taken care of.

    Use this when you have a byte string representing text that you need
    to make suitable for output to xml.  There are several cases where this
    is the case.  For instance, if you need to transform some strings encoded
    in latin1 to utf8 for output::

        utf8_string = byte_string_to_xml(latin1_string, input_encoding='latin-1')

    If you already have strings in the proper encoding you may still want to
    use this function to remove control characters::

        cleaned_string = byte_string_to_xml(string, input_encoding='utf-8', output_encoding='utf-8')

    .. seealso::

        :func:`unicode_to_xml`
            for other ideas on using this function
    '''
    if not isinstance(byte_string, str):
        raise XmlEncodeError(_('byte_string_to_xml can only take a byte'
                ' string as its first argument.  Use unicode_to_xml for'
                ' unicode strings'))

    # Decode the string into unicode
    u_string = unicode(byte_string, input_encoding, errors)
    return unicode_to_xml(u_string, encoding=output_encoding,
            attrib=attrib, control_chars=control_chars)

def xml_to_byte_string(byte_string, input_encoding='utf-8', errors='replace',
        output_encoding='utf-8'):
    '''Transform a byte string from an xml file into unicode

    :arg byte_string: byte string to decode
    :kwarg input_encoding: encoding that the byte string is in
    :kwarg errors: What to do if not every character is decodable using
        :attr:`encoding`.  See the :func:`to_unicode` docstring for
        legal values.
    :kwarg output_encoding: Encoding for the output byte string
    :returns: unicode string decoded from :attr:`byte_string`

    This function attempts to reverse what :func:`unicode_to_xml` does.
    It takes a byte string (presumably read in from an xml file) and expands
    all the html entities into unicode characters and decodes the bytes into
    a unicode string.  One thing it cannot do is restore any control
    characters that were removed prior to inserting into the file.  If you
    need to keep such characters you need to use func:`xml_to_bytes` and
    :func:`bytes_to_xml` instead.
    '''
    string = xml_to_unicode(byte_string, input_encoding, errors)
    return to_bytes(string, output_encoding, errors)

def bytes_to_xml(byte_string, *args, **kwargs):
    '''Return a byte string encoded so it is valid inside of any xml file

    :arg byte_string: byte string to transform
    :arg *args, **kwargs: extra arguments to this function are passed on to the
        function actually implementing the encoding.  You can use this to tweak
        the output in some cases but, as a general rule, you shouldn't because
        the underlying encoding function is not guaranteed to remain the same.
    :rtype: byte string consisting of all ASCII characters
    :returns: byte string representation of the input.  This will be encoded
        using base64.

    This function is made especially to put binary information into xml
    documents.

    This function is intended for encoding things that must be preserved
    byte-for-byte.  If you want to encode a byte string that's text and don't
    mind losing the actual bytes you probably want to try byte_string_to_xml()
    or guess_bytes_to_xml().

    .. note:: Although the current implementation uses base64.b64encode and
        there's no plans to change it, that isn't guaranteed.  If you want to
        make sure that you can encode and decode these messages it's best to
        use :func:`xml_to_bytes` if you use this function to encode.
    '''
    # Can you do this yourself?  Yes, you can.
    return b64encode(byte_string, *args, **kwargs)

# :C0103: Why do this?  Function calls in CPython are rather expensive.  We
#   start by defining this as a function so we can get a docstring.  Then we
#   redefine it as an attribute to save one useless function call.
#pylint:disable-msg=C0103
bytes_to_xml = b64encode

def xml_to_bytes(byte_string, *args, **kwargs):
    '''Decode as string encoded using :func:`bytes_to_xml`

    :arg byte_string: byte string to transform.  This should be a base64
        encoded sequence of bytes originally generated by :func:`bytes_to_xml`.
    :arg *args, **kwargs: extra arguments to this function are passed on to the
        function actually implementing the encoding.  You can use this to tweak
        the output in some cases but, as a general rule, you shouldn't because
        the underlying encoding function is not guaranteed to remain the same.
    :rtype: byte string
    :returns: byte string that's the decoded input.

    If you've got fields in an xml document that were encoded with
    :func:`bytes_to_xml` then you want to use this function to undecode them.
    It converts a base64 encoded string into a byte string.

    .. note:: Although the current implementation uses base64.b64decode and
        there's no plans to change it, that isn't guaranteed.  If you want to
        make sure that you can encode and decode these messages it's best to
        use :func:`bytes_to_xml` if you use this function to decode.
    '''
    return b64decode(byte_string, *args, **kwargs)

# :C0103: Why do this?  Function calls in CPython are rather expensive.  We
#   start by defining this as a function so we can get a docstring.  Then we
#   redefine it as an attribute to save one useless function call.
#pylint:disable-msg=C0103
xml_to_bytes = b64decode

def guess_encoding_to_xml(string, output_encoding='utf-8', attrib=False,
        control_chars='replace'):
    '''Return a byte string suitable for inclusion in xml

    :arg string: unicode or byte string to be transformed into a byte string
        suitable for inclusion in xml.  If string is a byte string we attempt
        to guess the encoding.  If we cannot guess, we fallback to latin1.
    :kwarg output_encoding: Output encoding for the byte string.  This should
        match the encoding of your xml file.
    :kwarg attrib: If True, escape the item for use in an attribute.  If False
         default) escape the item for use in a text node.
    :returns: utf8 encoded byte string

    '''
    # Unicode strings can just be run through unicode_to_xml()
    if isinstance(string, unicode):
        return unicode_to_xml(string, encoding=output_encoding,
                attrib=attrib, control_chars=control_chars)

    # Guess the encoding of the byte strings
    input_encoding = guess_encoding(string)

    # Return the new byte string
    return byte_string_to_xml(string, input_encoding=input_encoding,
            errors='replace', output_encoding=output_encoding,
            attrib=attrib, control_chars=control_chars)

def getwriter(encoding):
    '''Return a :class:`codecs.StreamWriter` that resists tracing back.

    This is a reimplemetation of :func:`codecs.getwriter` that resists issuing
    tracebacks.  The :class:`~codecs.StreamWriter` that is returned uses
    :func:`kitchen.text.converters.to_bytes` to convert :class:`unicode`
    strings into byte :class:`str`.  The departures from
    :func:`codecs.getwriter` are:

    1) The :class:`~codecs.StreamWriter` that is returned will take byte
        :class:`str` as well as :class:`unicode` strings.  byte :class:`str`
        will be passed through unmodified.
    2) The default error handler for unknown bytes is to ``replace`` the bytes
        with the unknown character ('?' in most ascii-based encodings, u'�' in
        the utf encodings).  :func:`codecs.getwriter` defaults to ``strict``.
        Like :class:`codecs.StreamWriter`, the returned
        :class:`~codecs.StreamWriter` can change have its error handler
        changed in code by setting stream.errors = 'new_handler_name'

    :arg encoding: Encoding to use for transforming the :class:`unicode`
        characters into bytes.
    :rtype: `codecs.StreamWriter` class
    :returns: `~codecs.StreamWriter` that you can instantiate to wrap output
        streams to automatically translate bytes into :attr:`encoding`.

    Example usage::

        $ LC_ALL=C python
        >>> import sys
        >>> from kitchen.text.converters import getwriter
        >>> UTF8Writer = getwriter('utf-8')
        >>> unwrapped_stdout = sys.stdout
        >>> sys.stdout = UTF8Writer(unwrapped_stdout)
        >>> print 'caf\\xc3\\xa9'
        café
        >>> print u'caf\\xe9'
        café
        >>> ASCIIWriter = getwriter('ascii')
        >>> sys.stdout = ASCIIWriter(unwrapped_stdout)
        >>> print 'caf\\xc3\\xa9'
        café
        >>> print u'caf\\xe9'
        caf?

    .. seealso::
        :class:`codecs.StreamWriter`
            password
        :func:`codecs.getwriter`
            password
        `Print Fails <http://wiki.python.org/moin/PrintFails>`_ on the python wiki
            password

    .. versionadded:: kitchen 0.2a2, API: kitchen.text 1.1.0
    '''
    class _StreamWriter(codecs.StreamWriter):
        # :W0223: We don't need to implement all methods of StreamWriter.
        #   This is not the actual class that gets used but a replacement for
        #   the actual class.
        # :C0111: We're implementing an API from the stdlib.  Just point
        #   people at that documentation instead of writing docstrings here.
        #pylint:disable-msg=W0223,C0111
        def __init__(self, stream, errors='replace'):
            codecs.StreamWriter.__init__(self, stream, errors)

        def encode(self, msg, errors='replace'):
            return (to_bytes(msg, encoding=self.encoding, errors=errors),
                    len(msg))

    _StreamWriter.encoding = encoding
    return _StreamWriter

def to_xml(string, encoding='utf-8', attrib=False, control_chars='ignore'):
    '''Deprecated: Use guess_encoding_to_xml() instead
    '''
    warnings.warn(_('kitchen.text.converters.to_xml is deprecated.  Use'
            ' kitchen.text.converters.guess_encoding_to_xml instead.'),
            DeprecationWarning, stacklevel=2)
    return guess_encoding_to_xml(string, output_encoding=encoding,
            attrib=attrib, control_chars=control_chars)

__all__ = ('byte_string_to_xml', 'bytes_to_xml', 'getwriter',
        'guess_encoding_to_xml', 'to_bytes', 'to_str', 'to_unicode',
        'to_utf8', 'to_xml', 'unicode_to_xml', 'xml_to_byte_string',
        'xml_to_bytes', 'xml_to_unicode')
