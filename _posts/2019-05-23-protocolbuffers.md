---
layout: post
title:  "如何编译C#版本的Protocol Buffers与gRPC服务端，客户端代码"
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

protoc.exe可以在以下地址下载：https://github.com/protocolbuffers/protobuf/releases

如果使用nuget安装过Google.Protobuf.Tools，在这个目录也可以找到protoc.exe
%UserProfile%\.nuget\packages\Google.Protobuf.Tools\3.7.0\tools\windows_x64\protoc.exe

最简单的编译bat可以这样写：

```bash
protoc --csharp_out=./ greet.proto
```

--csharp_out是必选参数， 还有一个-I为可选参数，默认为当前目录，指定代码目录

如果需要同时编译服务端和客户端代码，需要grpc_csharp_plugin，可以在Grpc.Tools nuget包中找到：
%UserProfile%\.nuget\packages\Grpc.Tools\1.20.0\tools\windows_x64\grpc_csharp_plugin.exe

```bash
set PLUGIN=%UserProfile%\.nuget\packages\Grpc.Tools\1.20.0\tools\windows_x64\grpc_csharp_plugin.exe
D:\Grpc\protoc-3.7.1-win64\bin\protoc.exe --csharp_out=./ greet.proto --grpc_out ./ --plugin=protoc-gen-grpc=%PLUGIN%
```

## 使用Visual Studio和Grpc.Tools自动编译

Grpc.Tools在1.17版之后，可以与MSBuild集成，自动根据proto文件编译生成C#代码。

生成的代码可以在obj/Debug/TARGET_FRAMEWORK文件夹中找到。

配置方式：

* 添加Grpc.Tools nuget包
* 在proto文件的属性中，将Build Action修改为Protobuf compiler
* Build Action如果设置为Content，Custom Tool设置为MSBuild:Compile也可
* 直接修改csproj文件，添加：

```xml
<Protobuf Include="Protos\greet.proto" GrpcServices="Client" />
```

> 注意：如果proto文件中使用了import导入其他proto文件，需要写入在Visual Studio中的完整路径，例如：
>
> ```java
> import "Protos/message.proto";
> ```