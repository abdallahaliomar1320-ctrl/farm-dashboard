<?php

namespace App\Support;

/**
 * تنفيذ TOTP (RFC 6238) بدون مكتبات خارجية — للتحقق بخطوة ثانية عند دخول المالك.
 */
class Totp
{
    public const PERIOD = 30;
    public const DIGITS = 6;

    /** توليد سر عشوائي بصيغة Base32 (160 بت) */
    public static function generateSecret(): string
    {
        return self::base32Encode(random_bytes(20));
    }

    /** حساب الرمز لسر معروف عند لحظة زمنية — يُستخدم في الاختبارات وفي العرض التجريبي */
    public static function code(string $secret, ?int $time = null): string
    {
        $time ??= time();
        $counter = intdiv($time, self::PERIOD);

        $binaryCounter = pack('N2', 0, $counter);
        $hash = hash_hmac('sha1', $binaryCounter, self::base32Decode($secret), true);

        $offset = ord($hash[19]) & 0x0F;
        $value = ((ord($hash[$offset]) & 0x7F) << 24)
            | (ord($hash[$offset + 1]) << 16)
            | (ord($hash[$offset + 2]) << 8)
            | ord($hash[$offset + 3]);

        return str_pad((string) ($value % (10 ** self::DIGITS)), self::DIGITS, '0', STR_PAD_LEFT);
    }

    /** التحقق من رمز مع قبول انحراف ± 30 ثانية */
    public static function verify(string $secret, string $code): bool
    {
        $code = trim($code);
        if (! preg_match('/^\d{6}$/', $code)) {
            return false;
        }
        foreach ([0, -1, 1] as $drift) {
            if (hash_equals(self::code($secret, time() + $drift * self::PERIOD), $code)) {
                return true;
            }
        }

        return false;
    }

    /** ربط تطبيق المصادقة عبر مسار otpauth:// القياسي */
    public static function uri(string $secret, string $accountName, string $issuer = 'لوحة المالك'): string
    {
        return sprintf(
            'otpauth://totp/%s:%s?secret=%s&issuer=%s&algorithm=SHA1&digits=%d&period=%d',
            rawurlencode($issuer),
            rawurlencode($accountName),
            $secret,
            rawurlencode($issuer),
            self::DIGITS,
            self::PERIOD,
        );
    }

    public static function base32Encode(string $bytes): string
    {
        $alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
        $output = '';
        $bits = 0;
        $value = 0;

        foreach (str_split($bytes) as $byte) {
            $value = ($value << 8) | ord($byte);
            $bits += 8;
            while ($bits >= 5) {
                $output .= $alphabet[($value >> ($bits - 5)) & 31];
                $bits -= 5;
            }
        }
        if ($bits > 0) {
            $output .= $alphabet[($value << (5 - $bits)) & 31];
        }

        return $output;
    }

    public static function base32Decode(string $b32): string
    {
        $alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
        $b32 = strtoupper(preg_replace('/[^A-Za-z2-7]/', '', $b32) ?? '');
        $output = '';
        $bits = 0;
        $value = 0;

        foreach (str_split($b32) as $char) {
            $pos = strpos($alphabet, $char);
            if ($pos === false) {
                continue;
            }
            $value = ($value << 5) | $pos;
            $bits += 5;
            if ($bits >= 8) {
                $output .= chr(($value >> ($bits - 8)) & 0xFF);
                $bits -= 8;
            }
        }

        return $output;
    }
}
