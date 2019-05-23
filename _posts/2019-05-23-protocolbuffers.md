---
layout: post
title:  "如何编译C#版本的 Protocol Buffers"
date:   2019-05-23
tags: 
    - gRPC
---

## 定义Protocol Buffers

message.proto

```java
syntax = "proto3";
package Greet;

// The request message containing the user's name.
message HelloRequest {
    string name = 1;
}

// The response message containing the greetings.
message HelloReply {
    string message = 1;
}
```

greet.proto

```java
syntax = "proto3";
package Greet;

option csharp_namespace = "Greet";

import "message.proto";

// The greeting service definition.
service Greeter {
  // Sends a greeting
  rpc SayHello (HelloRequest) returns (HelloReply) {}
}
```

csharp_namespace这个是针对C#独有的可选配置，如果namespace与package相同，可以不用写。

## 使用protoc手动编译



## 使用Visual Studio和Grpc.Tools自动编译