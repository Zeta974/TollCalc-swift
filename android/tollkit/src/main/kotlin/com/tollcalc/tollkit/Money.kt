package com.tollcalc.tollkit

import java.math.BigDecimal
import kotlin.math.abs

/**
 * An amount in euro cents. Toll prices are always handled as integers so that
 * sums are exact to the cent — no floating point is ever involved.
 */
@JvmInline
value class Money(val cents: Int) : Comparable<Money> {

    operator fun plus(other: Money): Money = Money(cents + other.cents)

    override fun compareTo(other: Money): Int = cents.compareTo(other.cents)

    /** Exact decimal value in euros. */
    val euros: BigDecimal get() = BigDecimal.valueOf(cents.toLong(), 2)

    /** French formatting as printed on the operators' grids, e.g. "58,20 €". */
    val formatted: String
        get() {
            val sign = if (cents < 0) "-" else ""
            val absolute = abs(cents)
            val remainder = absolute % 100
            return "$sign${absolute / 100},${if (remainder < 10) "0" else ""}$remainder €"
        }

    override fun toString(): String = formatted

    companion object {
        val ZERO = Money(0)
    }
}

fun Iterable<Money>.sum(): Money = fold(Money.ZERO, Money::plus)
