---
pubDatetime: 2025-03-16
tags: [".NET", "C#"]
slug: implementing-aes-encryption-csharp
source: milanjovanovic.tech
title: 在C#中实现安全的AES加密：保护敏感数据的终极指南
description: 探索如何在C#中实现AES加密以保护API密钥和密码等敏感数据，涵盖加密、解密的实际代码示例及关键管理最佳实践。
---

# 在C#中实现安全的AES加密：保护敏感数据的终极指南

在数字化时代，保护API密钥和数据库密码等敏感数据至关重要。🔐 在这篇文章中，我们将探讨如何在C#中实施AES加密，以确保即使其他安全措施失效，数据仍保持不可读状态。

## 对称加密 vs 非对称加密

[对称加密](https://en.wikipedia.org/wiki/Symmetric-key_algorithm)（如AES）使用相同的密钥进行加密和解密，速度快，非常适合存储仅应用程序需要读取的数据。主要挑战在于安全地存储加密密钥。

[非对称加密](https://en.wikipedia.org/wiki/Public-key_cryptography)（如RSA）使用不同的密钥进行加密和解密，虽然较慢，但允许不共享秘密的各方之间进行安全通信。常见用途包括SSL/TLS和数字签名。

对于存储API密钥和应用程序秘密，对称加密的AES是适当选择。

![AES加密算法](https://www.milanjovanovic.tech/blogs/mnw_126/aes_encryption.png?imwidth=1920)

## AES加密实现

在C#中实现安全的[AES（高级加密标准）](https://en.wikipedia.org/wiki/Advanced_Encryption_Standard)加密，使用AES-256提供当前最强的安全性。

```csharp
public class Encryptor
{
    private const int KeySize = 256;
    private const int BlockSize = 128;

    public static EncryptionResult Encrypt(string plainText)
    {
        using var aes = Aes.Create();
        aes.KeySize = KeySize;
        aes.BlockSize = BlockSize;

        aes.GenerateKey();
        aes.GenerateIV();

        byte[] encryptedData;

        using (var encryptor = aes.CreateEncryptor())
        using (var msEncrypt = new MemoryStream())
        {
            using (var csEncrypt = new CryptoStream(msEncrypt, encryptor, CryptoStreamMode.Write))
            using (var swEncrypt = new StreamWriter(csEncrypt))
            {
                swEncrypt.Write(plainText);
            }

            encryptedData = msEncrypt.ToArray();
        }

        var result = EncryptionResult.CreateEncryptedData(
            encryptedData,
            aes.IV,
            Convert.ToBase64String(aes.Key)
        );

        return result;
    }
}

public class EncryptionResult
{
    public string EncryptedData { get; set; }
    public string Key { get; set; }

    public static EncryptionResult CreateEncryptedData(byte[] data, byte[] iv, string key)
    {
        var combined = new byte[iv.Length + data.Length];
        Array.Copy(iv, 0, combined, 0, iv.Length);
        Array.Copy(data, 0, combined, iv.Length, data.Length);

        return new EncryptionResult
        {
            EncryptedData = Convert.ToBase64String(combined),
            Key = key
        };
    }

    public (byte[] iv, byte[] encryptedData) GetIVAndEncryptedData()
    {
        var combined = Convert.FromBase64String(EncryptedData);

        var iv = new byte[16];
        var encryptedData = new byte[combined.Length - 16];

        Array.Copy(combined, 0, iv, 0, 16);
        Array.Copy(combined, 16, encryptedData, 0, encryptedData.Length);

        return (iv, encryptedData);
    }
}
```

### 解密实现

以下是对应的解密实现：

```csharp
public class Decryptor
{
    private const int KeySize = 256;
    private const int BlockSize = 128;

    public static string Decrypt(EncryptionResult encryptionResult)
    {
        var key = Convert.FromBase64String(encryptionResult.Key);
        var (iv, encryptedData) = encryptionResult.GetIVAndEncryptedData();

        using var aes = Aes.Create();
        aes.KeySize = KeySize;
        aes.BlockSize = BlockSize;
        aes.Key = key;
        aes.IV = iv;

        using var decryptor = aes.CreateDecryptor();
        using var msDecrypt = new MemoryStream(encryptedData);
        using var csDecrypt = new CryptoStream(msDecrypt, decryptor, CryptoStreamMode.Read);
        using var srDecrypt = new StreamReader(csDecrypt);

        try
        {
            return srDecrypt.ReadToEnd();
        }
        catch (CryptographicException ex)
        {
            throw new CryptographicException("Decryption failed", ex);
        }
    }
}
```

## 使用示例

以下是如何使用上述实现来加密和解密敏感数据的示例：

```csharp
// Encrypt sensitive data
var apiKey = "your-sensitive-api-key";
var encryptionResult = Encryptor.Encrypt(apiKey);

// Store encrypted data in database
SaveToDatabase(encryptionResult.EncryptedData);

// Store key in key vault
await keyVault.StoreKeyAsync("apikey_1", encryptionResult.Key);

// Later, decrypt when needed
var encryptedData = LoadFromDatabase();
var key = await keyVault.GetKeyAsync("apikey_1");

var result = new EncryptionResult
{
    EncryptedData = encryptedData,
    Key = key
};

var decrypted = Decryptor.Decrypt(result);
```

## 关键管理与总结

AES加密为敏感应用程序数据提供了强大的安全性。正确的关键管理至关重要。建议在生产中使用专用的关键存储服务，如[Azure Key Vault](https://learn.microsoft.com/en-us/azure/key-vault/)、[AWS Key Management Service](https://aws.amazon.com/kms/)和[HashiCorp Vault](https://www.vaultproject.io/)。

记住，**加密只是全面安全策略的一部分**。保持您的加密键与加密数据分开，并定期更换它们。
