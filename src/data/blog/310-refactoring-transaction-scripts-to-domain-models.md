---
pubDatetime: 2025-05-10
tags: [.NET, DDD, 重构, 企业级开发, 软件架构]
slug: refactoring-transaction-scripts-to-domain-models
source: https://www.milanjovanovic.tech/blog/from-transaction-scripts-to-domain-models-a-refactoring-journey
title: 从事务脚本到领域模型：一次重构的进化之旅
description: 结合实际项目案例，深入剖析事务脚本与领域模型的转变过程，帮助.NET及企业级开发者提升业务架构可维护性与扩展性。
---

# 从事务脚本到领域模型：一次重构的进化之旅

## 引言：写API，如何优雅处理复杂业务逻辑？🤔

在后端开发，尤其是 .NET 或企业级应用领域，我们经常会问自己：**“业务逻辑到底应该放在哪里？”**刚起步时，大家往往采用事务脚本（Transaction Script），简单直观；但随着业务增长，这种方案也许会让你掉进维护的“泥潭”。今天，我们就通过一个健身追踪App的实战案例，聊聊如何优雅地完成从事务脚本到领域模型（Domain Model）的重构进阶！

## 一、事务脚本：简单直观，但会越写越乱

### 什么是事务脚本？

事务脚本模式，是一种最直接的实现方式。每个用例（如新增运动记录）都对应一个独立的方法或类，里面包含了所有业务逻辑、数据校验、数据访问等操作。

#### 示例代码

```csharp
internal sealed class AddExercisesCommandHandler(
    IWorkoutRepository workoutRepository,
    IUnitOfWork unitOfWork)
    : ICommandHandler<AddExercisesCommand>
{
    public async Task<Result> Handle(
        AddExercisesCommand request,
        CancellationToken cancellationToken)
    {
        Workout? workout = await workoutRepository.GetByIdAsync(
            request.WorkoutId,
            cancellationToken);

        if (workout is null)
        {
            return Result.Failure(WorkoutErrors.NotFound(request.WorkoutId));
        }

        List<Error> errors = [];
        foreach (ExerciseRequest exerciseDto in request.Exercises)
        {
            if (exerciseDto.TargetType == TargetType.Distance &&
                exerciseDto.DistanceInMeters is null)
            {
                errors.Add(ExerciseErrors.MissingDistance);
                continue;
            }

            if (exerciseDto.TargetType == TargetType.Time &&
                exerciseDto.DurationInSeconds is null)
            {
                errors.Add(ExerciseErrors.MissingDuration);
                continue;
            }

            var exercise = new Exercise(
                Guid.NewGuid(),
                workout.Id,
                exerciseDto.ExerciseType,
                exerciseDto.TargetType,
                exerciseDto.DistanceInMeters,
                exerciseDto.DurationInSeconds);

            workouts.Exercises.Add(exercise);
        }

        if (errors.Count != 0)
        {
            return Result.Failure(new ValidationError(errors.ToArray()));
        }

        await unitOfWork.SaveChangesAsync(cancellationToken);

        return Result.Success();
    }
}
```

### 随着业务增长会出现的问题

- **逻辑逐渐膨胀**：需求一多，代码中各种 if、for、校验逻辑交织，一改就出Bug。
- **难以复用**：多个用例间重复逻辑难以共享。
- **测试困难**：依赖多，单元测试常常要模拟一堆外部依赖。

举个栗子，如果需要限制“每个训练最多只能有10个动作”，你可能会在事务脚本里加一堆判断，代码如下：

```csharp
// 省略前面代码...
if (workouts.Exercise.Count > 10)
{
    return Result.Failure(
        WorkoutErrors.MaxExercisesReached(workout.Id));
}
```

业务越来越复杂时，这种“堆砌”很快让代码失控。

## 二、领域模型：让业务逻辑回归业务

### 什么是领域模型？

领域模型（Domain Model）强调**用对象来承载和封装领域逻辑**，数据和行为合一。它让你的代码像讲故事一样贴近业务——这也是 DDD（领域驱动设计）的核心思想。

> “An object model of the domain that incorporates both behavior and data.”  
> —— Martin Fowler，《企业应用架构模式》

#### 如何重构？——把业务逻辑“下沉”到领域对象

我们将核心规则从事务脚本“搬”到 Workout 领域对象：

```csharp
public sealed class Workout
{
    private readonly List<Exercise> _exercises = [];

    // 构造函数和属性略

    public Result AddExercises(ExerciseModel[] exercises)
    {
        List<Error> errors = [];
        foreach (var exerciseModel in exercises)
        {
            if (exerciseModel.TargetType == TargetType.Distance &&
                exerciseModel.DistanceInMeters is null)
            {
                errors.Add(ExerciseErrors.MissingDistance);
                continue;
            }

            if (exerciseModel.TargetType == TargetType.Time &&
                exerciseModel.DurationInSeconds is null)
            {
                errors.Add(ExerciseErrors.MissingDuration);
                continue;
            }

            var exercise = new Exercise(
                Guid.NewGuid(),
                this.Id,
                exerciseModel.ExerciseType,
                exerciseModel.TargetType,
                exerciseModel.DistanceInMeters,
                exerciseModel.DurationInSeconds);

            _exercises.Add(exercise);

            if (_exercises.Count > 10)
            {
                return Result.Failure(
                    WorkoutErrors.MaxExercisesReached(this.Id));
            }
        }

        if (errors.Count != 0)
        {
            return Result.Failure(new ValidationError(errors.ToArray()));
        }

        return Result.Success();
    }
}
```

### 重构后的优势

- **聚合根保证一致性**：所有关于 Workout 的操作都走 AddExercises，不容易出错。
- **逻辑复用&解耦**：新需求只需复用/扩展领域对象。
- **更易测试**：可以独立单测 Workout 类，无需模拟一堆仓储和上下文。
- **代码更贴合业务语义**：读起来就是“动作如何添加到训练中”，沟通无障碍。

重构后，事务脚本只需协调调用：

```csharp
var exercises = request.Exercises.Select(e => e.ToModel()).ToArray();
var result = workout.AddExercises(exercises);
// 后续持久化等
```

## 三、实战建议：何时从事务脚本转向领域模型？

- 项目初期，**事务脚本简单高效**，适合快速落地 MVP。
- 随着业务规则复杂化、复用和一致性需求提升时，**逐步引入领域模型是明智之选**。
- 不必一开始就追求完美，可以“按需重构”，聚焦高复杂度领域。

## 结论&互动：你遇到过哪些“烂尾”的业务逻辑？👀

从事务脚本到领域模型，是 .NET/企业级开发者进阶架构设计能力的重要一步。合理选型、适时重构，让你的代码既能快速响应需求，又不失优雅与可维护性。

👉 **你的项目里，有哪些“难以维护”的业务逻辑？你是如何解决的？欢迎评论区一起讨论或分享你的经验！**

---

_如果觉得本文对你有帮助，记得点赞、收藏或转发给更多朋友！_ 🚀
