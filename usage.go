package main

import (
	"context"
	"strconv"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb/types"
)

var (
	usageTable      string
	dailyTokenLimit int
	dynamoClient    *dynamodb.Client
)

func today() string {
	return time.Now().UTC().Format("2006-01-02")
}

// getUsedToday returns userID's token count for today. A missing row (first
// request of the day) is 0, not an error.
func getUsedToday(ctx context.Context, userID string) (int, error) {
	out, err := dynamoClient.GetItem(ctx, &dynamodb.GetItemInput{
		TableName: aws.String(usageTable),
		Key: map[string]types.AttributeValue{
			"user_id": &types.AttributeValueMemberS{Value: userID},
			"date":    &types.AttributeValueMemberS{Value: today()},
		},
	})
	if err != nil {
		return 0, err
	}
	if out.Item == nil {
		return 0, nil
	}

	used, ok := out.Item["tokens_used"].(*types.AttributeValueMemberN)
	if !ok {
		return 0, nil
	}
	return strconv.Atoi(used.Value)
}

// recordUsage atomically adds tokens to today's counter for userID, creating
// the row (with a TTL a few days out) on first use of the day, and returns
// the new running total so the caller can report it back to the client
// without a separate read.
func recordUsage(ctx context.Context, userID string, tokens int) (int, error) {
	expiresAt := time.Now().UTC().Truncate(24 * time.Hour).Add(72 * time.Hour).Unix()

	out, err := dynamoClient.UpdateItem(ctx, &dynamodb.UpdateItemInput{
		TableName: aws.String(usageTable),
		Key: map[string]types.AttributeValue{
			"user_id": &types.AttributeValueMemberS{Value: userID},
			"date":    &types.AttributeValueMemberS{Value: today()},
		},
		UpdateExpression: aws.String("ADD tokens_used :n SET expires_at = if_not_exists(expires_at, :ttl)"),
		ExpressionAttributeValues: map[string]types.AttributeValue{
			":n":   &types.AttributeValueMemberN{Value: strconv.Itoa(tokens)},
			":ttl": &types.AttributeValueMemberN{Value: strconv.FormatInt(expiresAt, 10)},
		},
		ReturnValues: types.ReturnValueUpdatedNew,
	})
	if err != nil {
		return 0, err
	}

	newTotal, ok := out.Attributes["tokens_used"].(*types.AttributeValueMemberN)
	if !ok {
		return tokens, nil
	}
	return strconv.Atoi(newTotal.Value)
}
