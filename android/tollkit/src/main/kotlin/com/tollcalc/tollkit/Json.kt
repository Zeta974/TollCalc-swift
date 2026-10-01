package com.tollcalc.tollkit

/**
 * Minimal JSON reader for the tariff files, so TollKit depends on nothing but
 * the Kotlin standard library (and runs unchanged on Android and the JVM).
 *
 * Objects become `Map<String, Any?>`, arrays `List<Any?>`, integers `Long`,
 * other numbers `Double`.
 */
internal class JsonReader(private val text: String) {
    private var i = 0

    fun parse(): Any? {
        val value = readValue()
        skipWhitespace()
        if (i != text.length) fail("trailing characters")
        return value
    }

    private fun readValue(): Any? {
        skipWhitespace()
        if (i >= text.length) fail("unexpected end of input")
        return when (val c = text[i]) {
            '{' -> readObject()
            '[' -> readArray()
            '"' -> readString()
            't' -> literal("true", true)
            'f' -> literal("false", false)
            'n' -> literal("null", null)
            else -> if (c == '-' || c in '0'..'9') readNumber() else fail("unexpected '$c'")
        }
    }

    private fun readObject(): Map<String, Any?> {
        i++ // {
        val map = LinkedHashMap<String, Any?>()
        skipWhitespace()
        if (peek() == '}') { i++; return map }
        while (true) {
            skipWhitespace()
            if (peek() != '"') fail("expected a key")
            val key = readString()
            skipWhitespace()
            expect(':')
            map[key] = readValue()
            skipWhitespace()
            when (next()) {
                ',' -> continue
                '}' -> return map
                else -> fail("expected ',' or '}'")
            }
        }
    }

    private fun readArray(): List<Any?> {
        i++ // [
        val list = ArrayList<Any?>()
        skipWhitespace()
        if (peek() == ']') { i++; return list }
        while (true) {
            list.add(readValue())
            skipWhitespace()
            when (next()) {
                ',' -> continue
                ']' -> return list
                else -> fail("expected ',' or ']'")
            }
        }
    }

    private fun readString(): String {
        i++ // opening quote
        val sb = StringBuilder()
        while (true) {
            if (i >= text.length) fail("unterminated string")
            when (val c = text[i++]) {
                '"' -> return sb.toString()
                '\\' -> {
                    when (val e = next()) {
                        '"', '\\', '/' -> sb.append(e)
                        'b' -> sb.append('\b')
                        'f' -> sb.append('\u000C')
                        'n' -> sb.append('\n')
                        'r' -> sb.append('\r')
                        't' -> sb.append('\t')
                        'u' -> {
                            if (i + 4 > text.length) fail("bad unicode escape")
                            sb.append(text.substring(i, i + 4).toInt(16).toChar())
                            i += 4
                        }
                        else -> fail("bad escape '\\$e'")
                    }
                }
                else -> sb.append(c)
            }
        }
    }

    private fun readNumber(): Any {
        val start = i
        var isInteger = true
        while (i < text.length) {
            val c = text[i]
            if (c in '0'..'9' || c == '-' || c == '+') i++
            else if (c == '.' || c == 'e' || c == 'E') { isInteger = false; i++ }
            else break
        }
        val s = text.substring(start, i)
        return (if (isInteger) s.toLongOrNull() else s.toDoubleOrNull()) ?: fail("bad number '$s'")
    }

    private fun literal(word: String, value: Any?): Any? {
        if (!text.startsWith(word, i)) fail("unexpected token")
        i += word.length
        return value
    }

    private fun skipWhitespace() {
        while (i < text.length && text[i].isWhitespace()) i++
    }

    private fun peek(): Char = if (i < text.length) text[i] else fail("unexpected end of input")

    private fun next(): Char = peek().also { i++ }

    private fun expect(c: Char) {
        if (next() != c) fail("expected '$c'")
    }

    private fun fail(message: String): Nothing = throw IllegalArgumentException("Invalid JSON at offset $i: $message")
}
